"""
NotificationConfig データクラスと merge_notification_config 純粋関数。

3層マージ: 環境変数 → site plugin_config → NOTIFICATION_OVERRIDE_DISABLED オーバーライド
で通知チャネル設定を解決する。

Requirements: 3.2, 4.1, 4.2, 4.3, 4.4, 4.5, 9.4
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class NotificationConfig:
    """通知チャネルの設定情報。"""

    slack_enabled: bool = False
    slack_webhook_url: str | None = None
    slack_channel: str = "#alerts"
    email_enabled: bool = True
    email_recipients: list[str] = field(default_factory=list)
    suppression_window_hours: int = 24


def merge_notification_config(
    customer_email: str,
    site_config: dict | None = None,
) -> NotificationConfig:
    """3層マージで NotificationConfig を生成する純粋関数。

    マージ優先順位: NOTIFICATION_OVERRIDE_DISABLED > site plugin_config > グローバル環境変数

    メール受信者の解決順序 (Req 3.2, 4.3):
    1. Customer.email をベース受信者として email_recipients の先頭に配置
    2. site plugin_config の additional_email_recipients を追加
    3. 重複を除去

    Args:
        customer_email: Customer.email (ベース受信者)
        site_config: MonitoringSite.plugin_config dict (nullable)

    Returns:
        マージ済み NotificationConfig
    """
    # Layer 1: グローバル環境変数
    slack_webhook_url = os.environ.get("NOTIFICATION_SLACK_WEBHOOK_URL") or None
    slack_channel = os.environ.get("NOTIFICATION_SLACK_CHANNEL", "#alerts")
    email_enabled = os.environ.get("NOTIFICATION_EMAIL_ENABLED", "true").lower() == "true"
    slack_enabled = os.environ.get("NOTIFICATION_SLACK_ENABLED", "false").lower() == "true"
    suppression_window_hours = int(
        os.environ.get("NOTIFICATION_SUPPRESSION_WINDOW_HOURS", "24")
    )

    additional_recipients: list[str] = []

    # Layer 2: サイト単位 plugin_config で上書き
    if site_config is not None:
        plugin_params = (
            site_config.get("params", {}).get("NotificationPlugin", {})
        )
        if plugin_params:
            if "slack_webhook_url" in plugin_params:
                slack_webhook_url = plugin_params["slack_webhook_url"] or None
            if "slack_channel" in plugin_params:
                slack_channel = plugin_params["slack_channel"]
            if "email_enabled" in plugin_params:
                email_enabled = bool(plugin_params["email_enabled"])
            if "slack_enabled" in plugin_params:
                slack_enabled = bool(plugin_params["slack_enabled"])
            if "suppression_window_hours" in plugin_params:
                suppression_window_hours = int(plugin_params["suppression_window_hours"])
            if "additional_email_recipients" in plugin_params:
                additional_recipients = list(plugin_params["additional_email_recipients"])

    # Layer 3: NOTIFICATION_OVERRIDE_DISABLED で全チャネル無効化
    override_disabled = os.environ.get("NOTIFICATION_OVERRIDE_DISABLED", "false").lower() == "true"
    if override_disabled:
        slack_enabled = False
        email_enabled = False

    # メール受信者: customer_email を先頭に、additional を追加、重複除去
    seen: set[str] = set()
    email_recipients: list[str] = []
    for addr in [customer_email] + additional_recipients:
        if addr and addr not in seen:
            seen.add(addr)
            email_recipients.append(addr)

    return NotificationConfig(
        slack_enabled=slack_enabled,
        slack_webhook_url=slack_webhook_url,
        slack_channel=slack_channel,
        email_enabled=email_enabled,
        email_recipients=email_recipients,
        suppression_window_hours=suppression_window_hours,
    )


def mask_webhook_url(url: str | None) -> str | None:
    """Webhook URL をマスクする。末尾8文字以外を '*' で置換。

    Args:
        url: マスク対象の URL (None 可)

    Returns:
        マスク済み URL。None の場合は None。
    """
    if url is None:
        return None
    if len(url) < 8:
        return "*" * len(url)
    return "*" * (len(url) - 8) + url[-8:]
