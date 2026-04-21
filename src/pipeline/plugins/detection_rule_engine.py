"""
DetectionRuleSet Engine — dynamic dark-pattern detection rules.

Supports built-in rule types (css_selector_exists, text_pattern_match,
price_threshold, element_attribute_check, dom_distance, custom_evaluator)
and a JSON-based rule definition format that can be loaded from a file or
from MonitoringSite.plugin_config without any Python code changes.

Requirements: 15.1–15.10, 16.1–16.5
"""

from __future__ import annotations

import importlib
import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Taxonomy
# ---------------------------------------------------------------------------

VALID_DARK_PATTERN_TYPES: frozenset[str] = frozenset(
    {
        "visual_deception",
        "hidden_subscription",
        "sneak_into_basket",
        "default_subscription",
        "confirmshaming",
        "distant_cancellation_terms",
        "hidden_fees",
        "urgency_pattern",
        "price_manipulation",
        "misleading_ui",
        "misleading_font_size",  # Requirement 17: 重要文言の小フォント表示
        "other",
    }
)


# ---------------------------------------------------------------------------
# DetectionRule dataclass
# ---------------------------------------------------------------------------


@dataclass
class DetectionRule:
    """Individual detection rule definition.

    Attributes:
        rule_id:               Unique identifier for the rule.
        rule_type:             One of the built-in evaluator types or
                               ``custom_evaluator``.
        target:                Detection target — CSS selector, text pattern,
                               data path, etc.  Interpretation depends on
                               ``rule_type``.
        condition:             Rule-specific condition parameters (dict).
        severity:              ``critical``, ``warning``, or ``info``.
        dark_pattern_category: Must be a value in ``VALID_DARK_PATTERN_TYPES``.
        enabled:               When False the rule is skipped entirely.
    """

    rule_id: str
    rule_type: str
    target: str
    condition: dict = field(default_factory=dict)
    severity: str = "warning"
    dark_pattern_category: str = "other"
    enabled: bool = True


# ---------------------------------------------------------------------------
# Rule loading
# ---------------------------------------------------------------------------


def _parse_rules_from_dict(data: dict) -> list[DetectionRule]:
    """Convert a raw dict (from JSON) into a list of DetectionRule objects."""
    rules: list[DetectionRule] = []
    for raw in data.get("rules", []):
        if not isinstance(raw, dict):
            logger.warning("Skipping non-dict rule entry: %r", raw)
            continue
        try:
            category = normalize_dark_pattern_type(
                raw.get("dark_pattern_category", "other")
            )
            rule = DetectionRule(
                rule_id=str(raw["rule_id"]),
                rule_type=str(raw.get("rule_type", "")),
                target=str(raw.get("target", "")),
                condition=raw.get("condition", {}),
                severity=str(raw.get("severity", "warning")),
                dark_pattern_category=category,
                enabled=bool(raw.get("enabled", True)),
            )
            rules.append(rule)
        except (KeyError, TypeError) as exc:
            logger.warning("Skipping invalid rule %r: %s", raw, exc)
    return rules


def load_detection_rules(
    site_config: Optional[dict] = None,
    global_rules_path: Optional[str] = None,
) -> list[DetectionRule]:
    """Load and merge global + site-specific detection rules.

    Merge order:
      1. Global rules from *global_rules_path* (or ``DETECTION_RULES_PATH``
         env var if *global_rules_path* is None).
      2. Site-specific rules from ``site_config["detection_rules"]``
         (overwrite by ``rule_id``).

    Invalid JSON is logged and silently skipped; built-in logic continues.

    Args:
        site_config:       ``MonitoringSite.plugin_config`` dict (optional).
        global_rules_path: Path to a global rules JSON file (optional).

    Returns:
        Merged list of DetectionRule objects.
    """
    # Resolve global rules path
    if global_rules_path is None:
        global_rules_path = os.environ.get("DETECTION_RULES_PATH")

    global_rules: list[DetectionRule] = []
    if global_rules_path:
        try:
            with open(global_rules_path, encoding="utf-8") as fh:
                data = json.load(fh)
            global_rules = _parse_rules_from_dict(data)
        except FileNotFoundError:
            logger.warning("Global rules file not found: %s", global_rules_path)
        except json.JSONDecodeError as exc:
            logger.error(
                "Invalid JSON in global rules file %s: %s", global_rules_path, exc
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Error loading global rules from %s: %s", global_rules_path, exc)

    # Site-specific rules
    site_rules: list[DetectionRule] = []
    if site_config:
        raw_site_rules = site_config.get("detection_rules")
        if raw_site_rules:
            if isinstance(raw_site_rules, str):
                try:
                    raw_site_rules = json.loads(raw_site_rules)
                except json.JSONDecodeError as exc:
                    logger.error("Invalid JSON in site detection_rules: %s", exc)
                    raw_site_rules = None
            if isinstance(raw_site_rules, dict):
                site_rules = _parse_rules_from_dict(raw_site_rules)
            elif isinstance(raw_site_rules, list):
                site_rules = _parse_rules_from_dict({"rules": raw_site_rules})

    # Merge: site rules overwrite global rules with the same rule_id
    merged: dict[str, DetectionRule] = {r.rule_id: r for r in global_rules}
    for rule in site_rules:
        merged[rule.rule_id] = rule

    return list(merged.values())


# ---------------------------------------------------------------------------
# Rule evaluators
# ---------------------------------------------------------------------------


def _eval_css_selector(
    rule: DetectionRule,
    page: Any,
    html: str,
    ctx_metadata: dict,
) -> Optional[dict]:
    """Check whether a CSS selector exists in *html* (simple regex heuristic).

    For a real Playwright page, the caller should use ``page.locator()``
    instead.  This fallback uses a regex search on the raw HTML string.
    """
    selector = rule.target
    # Simple heuristic: look for the selector as a class or id in the HTML
    pattern = re.compile(re.escape(selector), re.IGNORECASE)
    if pattern.search(html):
        return _build_violation(rule, {"selector": selector, "found_in_html": True})
    return None


def _eval_text_pattern(
    rule: DetectionRule,
    page: Any,
    html: str,
    ctx_metadata: dict,
) -> Optional[dict]:
    """Match a regex pattern against *html*."""
    pattern_str = rule.condition.get("pattern", rule.target)
    flags_str = rule.condition.get("flags", "")
    flags = 0
    if "IGNORECASE" in flags_str or "I" in flags_str:
        flags |= re.IGNORECASE
    if "MULTILINE" in flags_str or "M" in flags_str:
        flags |= re.MULTILINE

    try:
        pattern = re.compile(pattern_str, flags)
    except re.error as exc:
        logger.warning("Invalid regex in rule %s: %s", rule.rule_id, exc)
        return None

    match = pattern.search(html)
    if match:
        return _build_violation(
            rule, {"pattern": pattern_str, "matched_text": match.group(0)[:200]}
        )
    return None


def _eval_price_threshold(
    rule: DetectionRule,
    page: Any,
    html: str,
    ctx_metadata: dict,
) -> Optional[dict]:
    """Check whether any extracted price exceeds *condition.max_price*."""
    max_price = rule.condition.get("max_price")
    currency = rule.condition.get("currency", "")
    if max_price is None:
        logger.warning("Rule %s missing 'max_price' in condition", rule.rule_id)
        return None

    # Navigate the target path in ctx_metadata
    target_parts = rule.target.split(".")
    data: Any = ctx_metadata
    for part in target_parts:
        if isinstance(data, dict):
            data = data.get(part)
        else:
            data = None
        if data is None:
            break

    prices: list[float] = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                price_val = item.get("price") or item.get("amount")
                if isinstance(price_val, (int, float)):
                    prices.append(float(price_val))
    elif isinstance(data, (int, float)):
        prices.append(float(data))

    for price in prices:
        if price > max_price:
            return _build_violation(
                rule,
                {
                    "price": price,
                    "max_price": max_price,
                    "currency": currency,
                },
            )
    return None


def _eval_element_attribute(
    rule: DetectionRule,
    page: Any,
    html: str,
    ctx_metadata: dict,
) -> Optional[dict]:
    """Check whether an element attribute matches an expected value."""
    selector = rule.target
    attr_name = rule.condition.get("attribute", "")
    expected_value = rule.condition.get("value")

    # Heuristic: search for selector + attribute in raw HTML
    pattern = re.compile(
        re.escape(selector) + r"[^>]*" + re.escape(attr_name) + r'\s*=\s*["\']?'
        + re.escape(str(expected_value)),
        re.IGNORECASE | re.DOTALL,
    )
    if pattern.search(html):
        return _build_violation(
            rule,
            {
                "selector": selector,
                "attribute": attr_name,
                "expected_value": expected_value,
            },
        )
    return None


def _eval_dom_distance(
    rule: DetectionRule,
    page: Any,
    html: str,
    ctx_metadata: dict,
) -> Optional[dict]:
    """Check DOM distance stored in *ctx_metadata*."""
    distance_key = rule.condition.get("distance_key", "dom_distance")
    threshold = int(rule.condition.get("threshold", 20))
    distance = ctx_metadata.get(distance_key)
    if distance is None:
        return None
    if int(distance) >= threshold:
        return _build_violation(
            rule,
            {
                "distance": distance,
                "threshold": threshold,
                "distance_key": distance_key,
            },
        )
    return None


def _eval_custom(
    rule: DetectionRule,
    page: Any,
    html: str,
    ctx_metadata: dict,
) -> Optional[dict]:
    """Dynamically import and call a custom evaluator function.

    *rule.target* must be a dotted Python path, e.g.
    ``src.rules.merchant_specific.evaluate_cosmetics``.
    """
    target = rule.target
    try:
        module_path, func_name = target.rsplit(".", 1)
        module = importlib.import_module(module_path)
        func = getattr(module, func_name)
        result = func(rule, page, html, ctx_metadata)
        return result
    except (ImportError, AttributeError, ValueError) as exc:
        logger.warning("custom_evaluator %r failed to load: %s", target, exc)
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("custom_evaluator %r raised: %s", target, exc)
        return None


_EVALUATORS = {
    "css_selector_exists": _eval_css_selector,
    "text_pattern_match": _eval_text_pattern,
    "price_threshold": _eval_price_threshold,
    "element_attribute_check": _eval_element_attribute,
    "dom_distance": _eval_dom_distance,
    "custom_evaluator": _eval_custom,
}


def _build_violation(rule: DetectionRule, evidence: dict) -> dict:
    """Build a violation dict from a rule and evidence."""
    return {
        "violation_type": rule.rule_id,
        "severity": rule.severity,
        "dark_pattern_category": rule.dark_pattern_category,
        "rule_id": rule.rule_id,
        "rule_type": rule.rule_type,
        "evidence": evidence,
    }


def evaluate_rule(
    rule: DetectionRule,
    page: Any,
    html: str,
    ctx_metadata: dict,
) -> Optional[dict]:
    """Evaluate a single DetectionRule.

    Args:
        rule:         The rule to evaluate.
        page:         Playwright Page object (may be None for HTML-only rules).
        html:         Raw HTML string of the page.
        ctx_metadata: CrawlContext.metadata dict.

    Returns:
        A violation dict if the rule fires, otherwise None.
        Always returns None when ``rule.enabled`` is False.
    """
    if not rule.enabled:
        return None

    evaluator = _EVALUATORS.get(rule.rule_type)
    if evaluator is None:
        logger.warning("Unknown rule_type %r in rule %s", rule.rule_type, rule.rule_id)
        return None

    return evaluator(rule, page, html, ctx_metadata)


# ---------------------------------------------------------------------------
# Taxonomy normalisation
# ---------------------------------------------------------------------------


def normalize_dark_pattern_type(raw_type: str) -> str:
    """Normalise *raw_type* to a value in ``VALID_DARK_PATTERN_TYPES``.

    Normalisation steps:
      1. Strip whitespace.
      2. Lower-case.
      3. Replace spaces and hyphens with underscores.

    If the result is not in ``VALID_DARK_PATTERN_TYPES``, returns ``"other"``.

    Args:
        raw_type: Raw dark pattern type string.

    Returns:
        Normalised type string guaranteed to be in ``VALID_DARK_PATTERN_TYPES``.
    """
    normalised = raw_type.strip().lower().replace(" ", "_").replace("-", "_")
    if normalised in VALID_DARK_PATTERN_TYPES:
        return normalised
    return "other"
