# Implementation Plan: Advanced Dark Pattern Detection

## Overview

4つの新規プラグイン（CSSVisualPlugin, LLMClassifierPlugin, JourneyPlugin, UITrapPlugin）とDarkPatternScoreポストプロセスをCrawlPipelineに統合する。加えて、Hybrid Rule Engine（Built-in + LLM as a Judge）、Darksite検出基盤（Dense Vector + pHash）、ContentFingerprint（爆発防止付き）のコアインターフェースを実装する。

実装はPhase 1（純粋関数・ユーティリティ・コアインターフェース）→ Phase 2（プラグイン実装）→ Phase 3（DB・API・統合）の順で進め、各フェーズ内で依存関係を解決する。テストは pytest + Hypothesis を使用し、Python で実装する。

🚨 CTO Override 12件が全タスクに反映済み（RPC最適化、Middle-Out Truncation、DOM差分ノイズ排除、ヒューリスティックフォールバック、Max Pooling、Hybrid Rule Engine、TF-IDF廃止→Dense Vector、Fingerprint爆発防止、CoTフィールド順序、二重挿入禁止、指数バックオフリトライ、Fail-Fastバリデーション）。

## Tasks

- [x] 1. Phase 1: Pure functions and utilities
  - [x] 1.1 Implement WCAG contrast ratio calculation functions
    - Create `genai/src/pipeline/plugins/dark_pattern_utils.py`
    - Implement `relative_luminance(r, g, b) -> float` with sRGB gamma correction
    - Implement `contrast_ratio(fg: tuple, bg: tuple) -> float` using `(L1 + 0.05) / (L2 + 0.05)`
    - Implement `parse_rgba(color_str: str) -> tuple` to parse `rgb()` / `rgba()` CSS color strings
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [x]* 1.2 Write property tests for contrast ratio (Properties 1, 2)
    - **Property 1: コントラスト比の範囲不変条件**
    - Use `st.integers(0, 255)` for RGB values; assert `relative_luminance` returns 0.0–1.0, `contrast_ratio` returns 1.0–21.0
    - **Property 2: 低コントラスト閾値判定の正確性**
    - Generate color pairs, verify `contrast_ratio < 2.0` ↔ low contrast detection
    - **Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5, 1.4**
    - Test file: `genai/tests/test_dark_pattern_contrast.py`

  - [x] 1.3 Implement Middle-Out Truncation and HTML tag stripping
    - Add `strip_html_tags(html: str) -> str` to `dark_pattern_utils.py` — purge `<script>`, `<style>`, `<noscript>` and all HTML tags, preserve text nodes
    - Add `middle_out_truncate(text: str, max_tokens: int) -> str` — top 20% + bottom 30%, insert `[...中略...]` marker; return original if `len(text) <= max_tokens`
    - _Requirements: 2.3, 13.5_

  - [x]* 1.4 Write property tests for Middle-Out Truncation and HTML stripping (Properties 6, 12)
    - **Property 6: HTMLタグパージの完全性**
    - Generate random HTML strings; assert output contains no `<script>`, `<style>`, `<noscript>` content and no HTML tags
    - **Property 12: Middle-Out Truncation の保持特性**
    - Generate text + max_tokens; assert top 20% preserved, bottom 30% preserved, `[...中略...]` marker present when truncated
    - **Validates: Requirements 2.3, 13.5**
    - Test file: `genai/tests/test_dark_pattern_truncation.py`

  - [x] 1.5 Implement LLM response parsing utilities
    - Add `extract_json_block(text: str) -> dict` to `dark_pattern_utils.py` — extract JSON from markdown code blocks or raw JSON strings
    - Add `clamp_confidence(value: float) -> float` — clamp to [0.0, 1.0]
    - _Requirements: 8.3, 8.5_

  - [x]* 1.6 Write property tests for LLM parsing utilities (Properties 8, 9)
    - **Property 8: LLM confidence クランプ**
    - Generate arbitrary floats; assert clamped value in [0.0, 1.0], values already in range unchanged
    - **Property 9: LLM JSONブロック抽出**
    - Generate valid JSON, wrap in ` ```json ... ``` `; assert extracted object equals original
    - **Validates: Requirements 8.3, 8.5**
    - Test file: `genai/tests/test_dark_pattern_llm_utils.py`

  - [x] 1.7 Implement JourneyScript parsing and serialization
    - Add `parse_journey_script(raw: Any) -> list[dict]` to `dark_pattern_utils.py` — validate and parse JourneyScript JSON with step types (`add_to_cart`, `goto_checkout`, `click`, `wait`, `screenshot`) and assertion definitions
    - Add `serialize_journey_script(steps: list[dict]) -> str` — serialize steps to JSON string
    - _Requirements: 3.3, 3.4, 3.5, 3.8, 3.12_

  - [x]* 1.8 Write property test for JourneyScript round-trip (Property 13)
    - **Property 13: JourneyScript のラウンドトリップ**
    - Generate valid JourneyScript with random step types and assertions; assert `parse(serialize(parse(raw))) == parse(raw)`
    - **Validates: Requirements 3.12**
    - Test file: `genai/tests/test_dark_pattern_journey_utils.py`

  - [x] 1.9 Implement Confirmshaming pattern dictionary
    - Add `CONFIRMSHAMING_PATTERNS_JA` and `CONFIRMSHAMING_PATTERNS_EN` regex lists to `dark_pattern_utils.py`
    - Add `detect_confirmshaming(text: str) -> Optional[str]` — case-insensitive match against both JA and EN patterns, return matched pattern type or None
    - _Requirements: 10.1, 10.2, 10.3, 10.5_

  - [x]* 1.10 Write property test for Confirmshaming detection (Property 15)
    - **Property 15: コンファームシェイミングパターンマッチの一貫性**
    - Generate button text strings; assert case-insensitive consistency: if `t` matches, `t.upper()` and `t.lower()` also match
    - **Validates: Requirements 4.8, 4.9, 10.2, 10.3, 10.5**
    - Test file: `genai/tests/test_dark_pattern_confirmshaming.py`

  - [x] 1.11 Implement DarkPatternScore computation
    - Add `compute_dark_pattern_score(ctx: CrawlContext) -> CrawlContext` to `dark_pattern_utils.py`
    - Max Pooling over 4 subscores (css_visual, llm_classifier, journey, ui_trap)
    - Penalty baseline (default 0.15) for unexecuted plugins via `DARK_PATTERN_PENALTY_BASELINE` env var
    - Threshold check (default 0.6) via `DARK_PATTERN_SCORE_THRESHOLD` env var; add `high_dark_pattern_risk` violation when exceeded
    - Write `darkpattern_score` and `darkpattern_subscores` to `ctx.metadata`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

  - [x]* 1.12 Write property tests for DarkPatternScore (Properties 17, 18, 19)
    - **Property 17: DarkPatternScore の Max Pooling + ペナルティ正確性**
    - Generate 4 plugin executed/unexecuted states + subscores; assert max pooling with penalty baseline
    - **Property 18: DarkPatternScore の範囲不変条件**
    - Assert final score always in [0.0, 1.0]
    - **Property 19: DarkPatternScore の閾値判定**
    - Assert `score >= threshold` ↔ `high_dark_pattern_risk` violation added
    - **Validates: Requirements 5.2, 5.3, 5.4, 5.7**
    - Test file: `genai/tests/test_dark_pattern_score.py`

  - [x] 1.13 Implement DetectionRuleSet engine and dark_pattern_type taxonomy
    - Create `genai/src/pipeline/plugins/detection_rule_engine.py`
    - Define `VALID_DARK_PATTERN_TYPES` frozenset with 10 valid types + `other` fallback
    - Implement `DetectionRule` dataclass with `rule_id`, `rule_type`, `target`, `condition`, `severity`, `dark_pattern_category`, `enabled`
    - Implement `load_detection_rules(site_config, global_rules_path)` — merge global rules (from `DETECTION_RULES_PATH` env var) + site-specific rules (from `plugin_config["detection_rules"]`)
    - Implement `evaluate_rule(rule, page, html, ctx_metadata)` with built-in evaluators: `css_selector_exists`, `text_pattern_match`, `price_threshold`, `element_attribute_check`, `dom_distance`, `custom_evaluator`
    - Implement `normalize_dark_pattern_type(raw_type) -> str` — normalize to valid types, fallback to `other`
    - JSON validation with safe fallback (invalid JSON → log error, continue with built-in logic only)
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 15.7, 15.8, 15.9, 15.10, 16.1, 16.2, 16.3, 16.4, 16.5_

  - [x]* 1.14 Write property tests for DetectionRuleSet and taxonomy (Properties 23, 24, 25, 26)
    - **Property 23: DetectionRuleSet のバリデーションと安全なフォールバック**
    - Generate invalid JSON; assert validation error logged and built-in logic continues
    - **Property 24: DetectionRule 評価の正確性**
    - Generate enabled/disabled rules; assert enabled rules evaluate, disabled return None
    - **Property 25: dark_pattern_type 正規化の冪等性**
    - Generate arbitrary strings; assert output in VALID_DARK_PATTERN_TYPES, valid inputs unchanged, invalid → "other"
    - **Property 26: グローバルルール + サイト固有ルールのマージ正確性**
    - Generate global + site rule sets; assert merge overwrites by rule_id, adds new rules
    - **Validates: Requirements 15.5, 15.6, 15.7, 15.9, 15.10, 16.1, 16.2, 16.5**
    - Test file: `genai/tests/test_dark_pattern_rule_engine.py`

  - [x] 1.15 Implement Hybrid Rule Engine (Built-in + Dynamic LLM)
    - Update `genai/src/rules/engine.py` — RuleEngine with 2-phase execution: Built-in Rules → Dynamic LLM Rules
    - Built-in Rules: BaseContractRule registry + dynamic module loading + category filter
    - Dynamic LLM Rules: DynamicRuleProvider protocol → DynamicLLMValidatorPlugin delegation
    - 🚨 CTO Override #6: ルール追加は DB 登録のみ（Pythonファイル不要）。LLM as a Judge。
    - _Requirements: 15.1, 15.4, 15.5, 15.11_

  - [x] 1.16 Implement DynamicLLMValidatorPlugin (LLM as a Judge)
    - Update `genai/src/rules/dynamic_llm_validator.py` — CrawlPlugin integration
    - DB からアクティブルールをロード → LLM Judge で順次評価 → violations 追加
    - HTMLタグパージ (`_strip_html_to_text`) + Middle-Out Truncation (`_middle_out_truncate`)
    - 🚨 CTO Override #9: CoT フィールド順序（reasoning → evidence → confidence → compliant）
    - 🚨 CTO Override #10: 二重挿入禁止（{page_text} replace のみ、末尾追加なし）
    - 🚨 CTO Override #11: 指数バックオフ3回リトライ（tenacity）
    - _Requirements: 8.2, 8.7, 13.5, 13.6, 13.7_

  - [x] 1.17 Implement DynamicComplianceRule SQLAlchemy model and Pydantic schemas
    - `genai/src/rules/models.py` — DynamicComplianceRuleModel（DB自然言語ルール）
    - `genai/src/rules/schemas.py` — RuleSeverity/DarkPatternCategory Enum、LLMJudgeVerdict（CoT順序）、DynamicRuleCreate（{page_text} Fail-Fast）、DynamicRuleUpdate/Response
    - 🚨 CTO Override #7: Strict Mode 全フィールド必須、default 値禁止
    - 🚨 CTO Override #12: {page_text} Fail-Fast バリデーション
    - _Requirements: 8.7, 15.11, 16.1_

  - [x] 1.18 Implement ContentFingerprint model (pgvector)
    - `genai/src/rules/models.py` — ContentFingerprintModel
    - `text_embedding`: pgvector Vector(384) / JSONB フォールバック
    - `is_canonical_product` フラグ（🚨 CTO Override #8: 爆発防止）
    - `text_hash` (SHA-256)、`image_phashes` (JSONB)、`product_names`、`price_info`
    - 🚨 CTO Override #7: TF-IDF 廃止 → Dense Vector（all-MiniLM-L6-v2, 384次元）
    - _Requirements: (Darksite検出基盤)_

  - [x] 1.19 Implement Darksite detection protocol interfaces
    - `genai/src/darksite/protocol.py` — DarksiteDetectorProtocol、ContentEmbedder、FingerprintStore
    - DomainMatch、ContentMatch、ContentFingerprint、DarksiteReport dataclass
    - 🚨 CTO Override #7: Dense Vector セマンティック検索（コサイン類似度 ≥ 0.85）
    - _Requirements: (Darksite検出基盤)_

- [x] 2. Checkpoint — Phase 1 verification
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Phase 2: Plugin implementations
  - [x] 3.1 Implement CSSVisualPlugin
    - Create `genai/src/pipeline/plugins/css_visual_plugin.py`
    - Inherit `CrawlPlugin`; implement `should_run()` (check `pagefetcher_page` in metadata) and `execute()`
    - Define `BATCH_STYLE_JS` constant — single `page.evaluate()` TreeWalker script to collect all text element styles in one RPC (🚨 CTO Override)
    - Implement `_is_low_contrast(elem)` using `contrast_ratio()` with threshold 2.0
    - Implement `_is_tiny_font(elem, elements)` — detect font size < 25% of primary price font
    - Implement `_is_css_hidden(elem)` — detect offscreen (`left < -9000`), `opacity: 0`, `fontSize: 0`, `overflow: hidden` clipping, `display: none`, `visibility: hidden`
    - Implement `_calculate_deception_score(techniques) -> float` returning 0.0–1.0
    - Implement `_add_violations(ctx, techniques)` — add violations with `dark_pattern_category: visual_deception`, severity `warning`
    - Write `cssvisual_deception_score` and `cssvisual_techniques` to `ctx.metadata`
    - Error handling: catch exceptions, record in `ctx.errors`, set score to 0.0
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 1.10, 14.4_

  - [x]* 3.2 Write property tests for CSSVisualPlugin (Properties 3, 4, 5)
    - **Property 3: フォントサイズ異常検出の正確性**
    - Generate `cond_size` and `price_size`; assert `cond_size / price_size < 0.25` ↔ tiny font detected
    - **Property 4: CSS隠蔽検出の網羅性**
    - Generate CSS property sets with each hiding technique; assert detection for each condition
    - **Property 5: visual_deception_score の範囲不変条件**
    - Generate arbitrary technique lists; assert score in [0.0, 1.0]
    - **Validates: Requirements 1.4, 1.5, 1.6, 1.7, 1.8**
    - Test file: `genai/tests/test_dark_pattern_css_visual.py`

  - [x]* 3.3 Write unit tests for CSSVisualPlugin
    - Test `should_run()` returns True/False based on `pagefetcher_page` presence
    - Test `execute()` with mocked `page.evaluate()` returning sample element data
    - Test error handling: `page.evaluate()` failure records error and sets score to 0.0
    - Test unparseable CSS values are skipped with error recorded
    - _Requirements: 1.1, 1.2, 1.3, 1.10_
    - Test file: `genai/tests/test_dark_pattern_css_visual.py`

  - [x] 3.4 Implement LLMClassifierPlugin
    - Create `genai/src/pipeline/plugins/llm_classifier_plugin.py`
    - Inherit `CrawlPlugin`; implement `should_run()` (check `evidence_records` or `html_content` + `LLM_API_KEY`) and `execute()`
    - Implement provider abstraction: `_get_llm_client(provider: str)` supporting `gemini`, `claude`, `openai` via `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL` env vars
    - Implement `_extract_text(ctx)` — use `strip_html_tags()` on `html_content`, combine with OCR text from `evidence_records`
    - Implement `_split_chunks(text)` — split text respecting `LLM_MAX_INPUT_TOKENS` (default 4000) with `middle_out_truncate()`
    - Implement `_call_llm(chunk, screenshots)` — send prompt with structured JSON output format, support multimodal (screenshots) when available
    - Implement call counting with `LLM_MAX_CALLS_PER_CRAWL` (default 5); set `llmclassifier_calls_limited: True` when exceeded
    - Parse responses with `extract_json_block()`, clamp confidence with `clamp_confidence()`
    - Add violations when `confidence >= 0.7` and `is_subscription == True`, with `dark_pattern_category: hidden_subscription`, severity `warning`
    - Record token usage in `llmclassifier_token_usage` metadata
    - Error handling: API timeout/auth/rate-limit errors recorded in `ctx.errors`, pipeline continues
    - 🚨 CTO Override #9: LLM Structured Outputs は CoT フィールド順序（reasoning → evidence → confidence → compliant）
    - 🚨 CTO Override #10: プロンプト構築で二重挿入禁止（{page_text} replace のみ）
    - 🚨 CTO Override #11: 外部API呼び出しに指数バックオフ3回リトライ（tenacity）
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10, 2.11, 2.12, 2.13, 2.14, 8.1, 8.2, 8.3, 8.4, 8.5, 8.7, 13.1, 13.2, 13.3, 13.4, 13.5, 13.6, 13.7, 14.3_

  - [x]* 3.5 Write property tests for LLMClassifierPlugin (Properties 7, 10, 11)
    - **Property 7: LLM分類結果のラウンドトリップ**
    - Generate valid classification result objects; assert JSON round-trip equivalence
    - **Property 10: LLM confidence 閾値による violations 追加**
    - Generate result lists with varying confidence/is_subscription; assert only `confidence >= 0.7 and is_subscription` results added to violations
    - **Property 11: LLM API 呼び出し上限**
    - Generate chunk lists and max_calls; assert call count <= max_calls, `calls_limited` flag set when exceeded
    - **Validates: Requirements 8.6, 2.14, 2.10, 2.11, 13.1**
    - Test file: `genai/tests/test_dark_pattern_llm_classifier.py`

  - [x]* 3.6 Write unit tests for LLMClassifierPlugin
    - Test `should_run()` True/False conditions (evidence_records, html_content, LLM_API_KEY)
    - Test provider switching (gemini/claude/openai) with mocked API clients
    - Test multimodal input when screenshots exist
    - Test JSON parse failure handling
    - Test rate limit and timeout error handling
    - _Requirements: 2.1, 2.2, 2.5, 2.6, 2.7, 2.8, 2.9, 2.12_
    - Test file: `genai/tests/test_dark_pattern_llm_classifier.py`

  - [x] 3.7 Implement JourneyPlugin
    - Create `genai/src/pipeline/plugins/journey_plugin.py`
    - Inherit `CrawlPlugin`; implement `should_run()` (check `plugin_config.JourneyPlugin.journey_script`) and `execute()`
    - Use `parse_journey_script()` to parse config
    - Implement `_capture_visible_snapshot(page)` — use `page.locator()` + `isVisible()` for visible elements only (🚨 CTO Override: no raw HTML diff)
    - Implement `_execute_step(page, step)` with selector click + `_get_role_fallback()` heuristic (🚨 CTO Override)
    - Implement `_get_role_fallback(page, step)` — `get_by_role("button", name=...)` patterns for each step type
    - Implement assertion evaluators: `_eval_no_new_fees()` (currency regex match on visible text), `_eval_no_upsell_modal()` (dialog/modal/popup locators), `_eval_no_preselected_subscription()` (checked checkbox/radio locators)
    - Capture before/after screenshots as `journey_{step_name}_before` / `journey_{step_name}_after` VariantCaptures
    - Write `journey_steps` and `journey_dom_diffs` to `ctx.metadata`
    - Error handling: invalid JSON → errors + skip; step execution error → errors + skip remaining steps
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10, 3.11, 3.13, 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_

  - [x]* 3.8 Write unit tests for JourneyPlugin
    - Test `should_run()` True/False based on plugin_config
    - Test step execution with mocked Playwright page (click, wait, screenshot)
    - Test heuristic fallback when selector not found
    - Test each assertion type (no_new_fees, no_upsell_modal, no_preselected_subscription)
    - Test invalid JourneyScript JSON error handling
    - Test step execution timeout error handling
    - _Requirements: 3.1, 3.2, 3.9, 3.10, 3.11_
    - Test file: `genai/tests/test_dark_pattern_journey.py`

  - [x] 3.9 Implement UITrapPlugin
    - Create `genai/src/pipeline/plugins/ui_trap_plugin.py`
    - Inherit `CrawlPlugin`; implement `should_run()` (check `html_content` + `pagefetcher_page`) and `execute()`
    - Implement `_detect_preselected_checkboxes(page)` — find `input[type="checkbox"]:checked` with paid service labels, add `sneak_into_basket` violations (severity `warning`)
    - Implement `_detect_default_subscription_radios(page)` — find radio groups where subscription option is default-selected before single-purchase, add `default_subscription` violations (severity `warning`)
    - Implement `_detect_distant_cancellation(page)` — measure DOM distance between subscription selector and cancellation terms, threshold from config (default 20), add `distant_cancellation_terms` violations (severity `info`)
    - Implement `_detect_confirmshaming(page)` — use `detect_confirmshaming()` utility on button texts, add `confirmshaming` violations (severity `warning`)
    - Write `uitrap_detections` to `ctx.metadata`
    - Error handling: DOM traversal errors recorded in `ctx.errors`, partial results preserved
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 4.10, 4.11, 14.3, 14.5_

  - [x]* 3.10 Write property test for UITrapPlugin (Property 16)
    - **Property 16: DOM距離閾値判定**
    - Generate non-negative integer distances and positive integer thresholds; assert `d >= threshold` ↔ `distant_cancellation_terms` violation detected
    - **Validates: Requirements 4.7**
    - Test file: `genai/tests/test_dark_pattern_ui_trap.py`

  - [x]* 3.11 Write unit tests for UITrapPlugin
    - Test `should_run()` True/False conditions
    - Test preselected checkbox detection with mocked page
    - Test default subscription radio detection
    - Test confirmshaming detection with JA and EN patterns
    - Test DOM distance measurement and threshold
    - Test error handling during DOM traversal
    - _Requirements: 4.1, 4.2, 4.3, 4.5, 4.7, 4.8, 4.11_
    - Test file: `genai/tests/test_dark_pattern_ui_trap.py`

- [x] 4. Checkpoint — Phase 2 verification
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Phase 3: Integration
  - [x] 5.1 Extend DB models and create Alembic migration
    - Add `dark_pattern_score` (Float, nullable), `dark_pattern_subscores` (JSONB, nullable), `dark_pattern_types` (JSONB, nullable) columns to `VerificationResult` in `genai/src/models.py`
    - Add `dark_pattern_category` (String(50), nullable) column to `Violation` in `genai/src/models.py`
    - Add `merchant_category` (String(50), nullable) column to `MonitoringSite` in `genai/src/models.py`
    - Create `dynamic_compliance_rules` table (from `genai/src/rules/models.py` DynamicComplianceRuleModel)
    - Create `content_fingerprints` table (from `genai/src/rules/models.py` ContentFingerprintModel) with pgvector Vector(384) for `text_embedding`
    - Create Alembic migration with upgrade (add all columns + tables) and downgrade (drop all)
    - 🚨 CTO Override #6: DynamicComplianceRule テーブルで LLM as a Judge ルールを DB 管理
    - 🚨 CTO Override #7: ContentFingerprint に Dense Vector（384次元）カラム
    - 🚨 CTO Override #8: `is_canonical_product` フラグで爆発防止
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 15.1_

  - [x] 5.2 Implement API endpoints
    - Create `genai/src/api/dark_patterns.py` with FastAPI router
    - Implement `GET /api/sites/{site_id}/dark-patterns` — return latest DarkPatternResponse (score, subscores, detected_patterns, detected_at)
    - Implement `GET /api/sites/{site_id}/dark-patterns/history` — return paginated DarkPatternHistoryResponse (limit/offset, default limit=50)
    - Handle 404 for missing site, null response for no detection results
    - Register router in `genai/src/main.py`
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6_

  - [x]* 5.3 Write property tests for API and violation format (Properties 20, 21, 22)
    - **Property 20: 違反レコードの通知連携フォーマット**
    - Generate violations from each plugin; assert `violation_type`, `severity`, `dark_pattern_category` fields present with correct severity mapping
    - **Property 21: APIレスポンスの必須フィールド**
    - Generate VerificationResult with non-null dark_pattern_score; assert response contains all required fields
    - **Property 22: ページネーションの正確性**
    - Generate limit, offset, and record counts; assert `len(results) <= min(limit, total - offset)` and `total` matches
    - **Validates: Requirements 14.1–14.6, 12.2, 12.4**
    - Test file: `genai/tests/test_dark_pattern_api.py`

  - [x]* 5.4 Write unit tests for API endpoints
    - Test 404 for non-existent site
    - Test empty result (no dark pattern data)
    - Test normal response with score, subscores, patterns
    - Test history pagination with various limit/offset values
    - _Requirements: 12.1, 12.5, 12.6_
    - Test file: `genai/tests/test_dark_pattern_api.py`

  - [x] 5.5 Register plugins in CrawlPipeline stages
    - Register `JourneyPlugin` in `page_fetcher` stage after `PreCaptureScriptPlugin`, before `ModalDismissPlugin`
    - Register `CSSVisualPlugin` in `data_extractor` stage after `OCRPlugin`
    - Register `LLMClassifierPlugin` in `data_extractor` stage after `CSSVisualPlugin`
    - Register `UITrapPlugin` in `validator` stage after `ContractComparisonPlugin`
    - Add `compute_dark_pattern_score()` as post-process after all plugin stages complete, before reporter stage
    - Ensure all 4 plugins support `plugin_config` site-level override and `PIPELINE_DISABLED_PLUGINS` env var
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_

  - [x] 5.6 Wire DarkPatternScore results to DB storage
    - Update `DBStoragePlugin` to persist `darkpattern_score`, `darkpattern_subscores`, and detected pattern types from `ctx.metadata` to `VerificationResult` columns
    - Ensure `dark_pattern_category` is written to `Violation` records for all dark pattern violations
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 14.1, 14.6_

  - [x]* 5.7 Write integration tests for pipeline stage ordering and end-to-end flow
    - Test plugin execution order across all 4 stages matches design (Req 6.1–6.4)
    - Test DarkPatternScore post-process runs after all plugins and before reporter
    - Test full pipeline with mocked plugins produces correct `darkpattern_score` and violations in DB
    - Test `plugin_config` site-level disable/enable for each new plugin
    - Test `PIPELINE_DISABLED_PLUGINS` env var disables plugins globally
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_
    - Test file: `genai/tests/test_dark_pattern_integration.py`

- [x] 6. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests validate universal correctness properties from the design document
- All pure functions (Phase 1) are testable without Playwright mocks
- Phase 2 plugin tests use `unittest.mock` for Playwright page objects and LLM API clients
- Phase 3 integration tests use the existing test DB fixtures from `genai/tests/conftest.py`

---

## Phase 4: Requirement 17 — misleading_font_size 検出（追加要件）

- [x] 7. misleading_font_size 純粋関数の実装
  - [x] 7.1 重要キーワードリストと検出関数を `dark_pattern_utils.py` に追加
    - `IMPORTANT_KEYWORDS_JA`: 定期・自動更新・解約・手数料・縛り・違約金・特定商取引・重要事項・同意 等
    - `IMPORTANT_KEYWORDS_EN`: subscription, auto-renew, cancel, cancellation, refund, fee, charge, terms 等
    - `contains_important_keyword(text: str) -> bool`: 日英キーワードの存在チェック
    - `compute_median_font_size(elements: list[dict]) -> float`: 全要素フォントサイズ中央値算出
    - `detect_misleading_font_size(elem, median, ratio) -> bool`: 閾値 + キーワード2段階判定
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5_

  - [x] 7.2 `VALID_DARK_PATTERN_TYPES` に `misleading_font_size` を追加
    - `genai/src/pipeline/plugins/detection_rule_engine.py`
    - _Requirements: 17.9_

- [x] 8. CSSVisualPlugin の拡張
  - [x] 8.1 `execute()` にページ全体フォントサイズ中央値算出と misleading_font_size 検出を追加
    - `compute_median_font_size(elements)` でページ中央値を算出
    - 環境変数 `MISLEADING_FONT_SIZE_RATIO`（デフォルト 0.75）で閾値を設定
    - `detect_misleading_font_size()` で各要素を判定
    - _Requirements: 17.1, 17.2, 17.5_

  - [x] 8.2 `_build_misleading_font_technique()` メソッドを追加
    - fontSize・medianFontSize・ratio を証拠として記録
    - _Requirements: 17.5_

  - [x] 8.3 `_add_violations()` を更新
    - `misleading_font_size` 違反は `dark_pattern_category: "misleading_font_size"` を使用（visual_deception とは独立）
    - _Requirements: 17.6_

- [x] 9. LLMClassifierPlugin プロンプト拡張
  - [x] 9.1 `_PROMPT_TEMPLATE` に `misleading_font_size` 検出指示を追加
    - 検出対象として小フォント重要文言を明示
    - `dark_pattern_type` の有効値に `"misleading_font_size"` を追加
    - _Requirements: 17.7, 17.8_

- [x] 10. テスト追加
  - [x] 10.1 `test_dark_pattern_css_visual.py` に misleading_font_size テストを追加
    - `TestContainsImportantKeyword`: 日英キーワード検出ユニットテスト（7件）
    - `TestComputeMedianFontSize`: 中央値算出ユニットテスト（4件）
    - `TestDetectMisleadingFontSize`: 検出ロジックユニットテスト（5件）
    - `test_property_misleading_font_size_threshold`: Property 27 プロパティテスト
    - `test_css_visual_plugin_misleading_font_size_violation`: 統合テスト
    - 全 43 件通過確認済み
    - _Requirements: 17.2, 17.5_

- [x] 11. 最終チェックポイント — misleading_font_size 全体検証
  - 全テスト（43件）通過確認済み
  - design.md・tasks.md・requirements.md への反映完了
