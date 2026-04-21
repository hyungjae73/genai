"""
NotificationTemplateRenderer - 違反情報から Slack/メール通知メッセージを生成する。

Slack Block Kit 形式のペイロード生成（severity 色分け付き）と
メール通知の件名・本文生成を担当する。

Requirements: 2.2, 2.3, 3.3, 3.4, 5.1, 5.2, 5.3, 5.4, 5.5
"""

from __future__ import annotations

from typing import Protocol

from src.pipeline.plugins.notification_config import NotificationConfig


# Severity → Slack attachment color mapping
SEVERITY_COLORS: dict[str, str] = {
    "warning": "#FFA500",
    "critical": "#FF0000",
    "info": "#0000FF",
}

# Default color for unknown severity values
DEFAULT_COLOR = "#808080"


class SiteLike(Protocol):
    """Protocol for site objects (duck typing for MonitoringSite)."""

    name: str
    url: str


class NotificationTemplateRenderer:
    """違反情報から Slack/メール通知メッセージを生成する。"""

    def render_violation_fields(
        self, violation: dict, site: SiteLike
    ) -> dict[str, str]:
        """違反 dict からテンプレートフィールド値を抽出。欠損値は 'N/A'。

        Fields: site_name, site_url, violation_type, severity,
                detected_price, expected_price, evidence_url, detected_at
        """
        return {
            "site_name": getattr(site, "name", None) or "N/A",
            "site_url": getattr(site, "url", None) or "N/A",
            "violation_type": violation.get("violation_type") or "N/A",
            "severity": violation.get("severity") or "N/A",
            "detected_price": str(violation["detected_price"]) if "detected_price" in violation and violation["detected_price"] is not None else "N/A",
            "expected_price": str(violation["expected_price"]) if "expected_price" in violation and violation["expected_price"] is not None else "N/A",
            "evidence_url": violation.get("evidence_url") or "N/A",
            "detected_at": violation.get("detected_at") or "N/A",
        }

    def render_slack_payload(
        self,
        violations: list[dict],
        config: NotificationConfig,
        site: SiteLike,
    ) -> dict:
        """Slack Block Kit 形式のペイロードを生成。severity 色分け付き。

        複数違反を1つのペイロードにまとめる (Req 5.3)。
        """
        attachments: list[dict] = []

        for violation in violations:
            fields = self.render_violation_fields(violation, site)
            severity = fields["severity"]
            color = SEVERITY_COLORS.get(severity, DEFAULT_COLOR)

            text_parts = [
                f"*サイト名:* {fields['site_name']}",
                f"*違反種別:* {fields['violation_type']}",
                f"*重要度:* {fields['severity']}",
                f"*検出日時:* {fields['detected_at']}",
            ]
            if fields["detected_price"] != "N/A":
                text_parts.append(f"*検出価格:* {fields['detected_price']}")
            if fields["evidence_url"] != "N/A":
                text_parts.append(f"*証拠URL:* {fields['evidence_url']}")

            attachments.append({
                "color": color,
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "\n".join(text_parts),
                        },
                    }
                ],
            })

        return {
            "channel": config.slack_channel,
            "text": f"ダークパターン違反検出: {getattr(site, 'name', 'N/A')}",
            "attachments": attachments,
        }

    def render_email(
        self,
        violations: list[dict],
        config: NotificationConfig,
        site: SiteLike,
    ) -> tuple[str, str]:
        """(subject, body) タプルを返す。複数違反を1通にまとめる。

        件名形式: [決済条件監視] {severity}: {site_name} でダークパターン違反を検出
        severity は最も深刻な違反のものを使用する。
        """
        severity_priority = {"critical": 0, "warning": 1, "info": 2}
        worst_severity = "info"
        for v in violations:
            sev = v.get("severity", "info")
            if severity_priority.get(sev, 99) < severity_priority.get(worst_severity, 99):
                worst_severity = sev

        site_name = getattr(site, "name", None) or "N/A"
        site_url = getattr(site, "url", None) or "N/A"

        subject = f"[決済条件監視] {worst_severity}: {site_name} でダークパターン違反を検出"

        body_parts: list[str] = [
            f"サイト名: {site_name}",
            f"サイトURL: {site_url}",
            "",
            f"検出された違反: {len(violations)}件",
            "=" * 40,
        ]

        for i, violation in enumerate(violations, 1):
            fields = self.render_violation_fields(violation, site)
            body_parts.append(f"\n--- 違反 {i} ---")
            body_parts.append(f"違反種別: {fields['violation_type']}")
            body_parts.append(f"重要度: {fields['severity']}")
            body_parts.append(f"検出日時: {fields['detected_at']}")
            body_parts.append(f"検出価格: {fields['detected_price']}")
            body_parts.append(f"契約価格: {fields['expected_price']}")
            body_parts.append(f"証拠URL: {fields['evidence_url']}")

        body = "\n".join(body_parts)
        return subject, body
