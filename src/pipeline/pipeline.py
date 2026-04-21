"""
CrawlPipeline オーケストレータ。

4ステージ構成のパイプラインオーケストレータ。
各ステージを page_fetcher → data_extractor → validator → reporter の順で実行し、
プラグインの should_run() / execute() を制御する。

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from src.models import MonitoringSite
from src.pipeline.context import CrawlContext
from src.pipeline.plugin import CrawlPlugin
from src.pipeline.plugins.notification_plugin import NotificationPlugin
from src.pipeline.plugins.journey_plugin import JourneyPlugin
from src.pipeline.plugins.css_visual_plugin import CSSVisualPlugin
from src.pipeline.plugins.llm_classifier_plugin import LLMClassifierPlugin
from src.pipeline.plugins.ui_trap_plugin import UITrapPlugin
from src.pipeline.plugins.dark_pattern_utils import compute_dark_pattern_score

logger = logging.getLogger(__name__)

# Stage execution order (fixed)
STAGE_ORDER = ["page_fetcher", "data_extractor", "validator", "reporter"]

# Default reporter stage plugin order: DBStoragePlugin → AlertPlugin → NotificationPlugin
# Req 1.3: NotificationPlugin executes after AlertPlugin in the Reporter stage.
DEFAULT_REPORTER_PLUGINS = [
    "DBStoragePlugin",
    "ObjectStoragePlugin",
    "AlertPlugin",
    "NotificationPlugin",
]


class CrawlPipeline:
    """4ステージパイプラインオーケストレータ。

    ステージ実行順序:
        1. page_fetcher — ページ取得・ブラウザ操作
        2. data_extractor — データ抽出（構造化データ、OCR等）
        3. validator — 検証（契約比較、証拠保全）
        4. reporter — レポート（DB保存、ストレージ、アラート）

    エラーハンドリング:
        - プラグインエラー: ctx.errors に記録し、同一ステージ内の残りプラグインは継続
        - PageFetcher で html_content 未取得: data_extractor ステージをスキップ
        - 各ステージの開始/終了時刻・実行プラグイン名を metadata に記録
    """

    def __init__(
        self,
        stages: Optional[dict[str, list[CrawlPlugin]]] = None,
    ):
        """パイプラインを初期化する。

        Args:
            stages: ステージ名 → プラグインインスタンスリストの dict。
                    None の場合は空のステージ構成で初期化される。
                    _resolve_plugins() によるマージは Task 2.5 で実装予定。
        """
        if stages is None:
            stages = {name: [] for name in STAGE_ORDER}

        self._stages: dict[str, list[CrawlPlugin]] = {}
        for name in STAGE_ORDER:
            self._stages[name] = stages.get(name, [])

    async def run(self, ctx: CrawlContext) -> CrawlContext:
        """全ステージを順次実行し、最終的な CrawlContext を返却する。

        各ステージの開始/終了時刻・実行プラグイン名を
        ctx.metadata["pipeline_stages"] に記録する。

        PageFetcher 完了後に ctx.html_content が None の場合、
        data_extractor ステージをスキップする。

        Args:
            ctx: パイプライン共有コンテキスト

        Returns:
            全ステージ実行後の CrawlContext
        """
        if "pipeline_stages" not in ctx.metadata:
            ctx.metadata["pipeline_stages"] = {}

        for stage_name in STAGE_ORDER:
            # Skip data_extractor if html_content is None after page_fetcher
            if stage_name == "data_extractor" and ctx.html_content is None:
                logger.info(
                    "Skipping data_extractor stage: html_content is None"
                )
                ctx.metadata["pipeline_stages"][stage_name] = {
                    "skipped": True,
                    "reason": "html_content is None",
                }
                continue

            # Run compute_dark_pattern_score after validator, before reporter
            if stage_name == "reporter":
                ctx = compute_dark_pattern_score(ctx)

            ctx = await self._run_stage(stage_name, ctx)

        return ctx

    async def _run_stage(
        self, stage_name: str, ctx: CrawlContext
    ) -> CrawlContext:
        """単一ステージを実行する。

        ステージ内の各プラグインに対し should_run() を評価し、
        True のプラグインのみ execute() を呼び出す。
        プラグインがエラーを発生させた場合、ctx.errors に記録し
        同一ステージ内の残りプラグインの実行を継続する。

        Args:
            stage_name: ステージ名
            ctx: パイプライン共有コンテキスト

        Returns:
            ステージ実行後の CrawlContext
        """
        plugins = self._stages.get(stage_name, [])
        start_time = datetime.now(timezone.utc)
        executed_plugins: list[str] = []

        for plugin in plugins:
            if plugin.should_run(ctx):
                try:
                    ctx = await plugin.execute(ctx)
                    executed_plugins.append(plugin.name)
                except Exception as e:
                    ctx.errors.append(
                        {
                            "plugin": plugin.name,
                            "stage": stage_name,
                            "error": str(e),
                            "timestamp": datetime.now(
                                timezone.utc
                            ).isoformat(),
                        }
                    )
                    executed_plugins.append(plugin.name)
                    logger.error(
                        "Plugin %s in stage %s failed: %s",
                        plugin.name,
                        stage_name,
                        e,
                    )

        end_time = datetime.now(timezone.utc)

        ctx.metadata["pipeline_stages"][stage_name] = {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "executed_plugins": executed_plugins,
        }

        return ctx

def resolve_plugin_config(
    global_enabled: set[str],
    site_config: Optional[dict] = None,
    disabled_env: Optional[list[str]] = None,
) -> tuple[set[str], dict[str, dict]]:
    """3層プラグイン設定マージを実行する純粋関数。

    マージロジック:
        1. グローバル有効プラグインからスタート
        2. site_config.disabled でプラグイン無効化
        3. PIPELINE_DISABLED_PLUGINS 環境変数でプラグイン無効化
        4. site_config.enabled で追加有効化

    site_config が None の場合はグローバル設定から disabled_env を除外した結果を返す。

    Args:
        global_enabled: グローバルで有効なプラグイン名のセット
        site_config: サイト単位のプラグイン設定。形式:
            {"disabled": ["PluginName"], "enabled": ["PluginName"],
             "params": {"PluginName": {"key": "value"}}}
        disabled_env: PIPELINE_DISABLED_PLUGINS 環境変数から取得した
            無効化プラグイン名のリスト

    Returns:
        (enabled_plugins, merged_params) のタプル。
        enabled_plugins: マージ後の有効プラグイン名のセット
        merged_params: マージ後のプラグインパラメータ dict

    Requirements: 22.7, 22.8, 22.9, 22.10, 22.11, 22.12
    """
    if disabled_env is None:
        disabled_env = []

    # Step 1: Start with global enabled plugins
    enabled = set(global_enabled)

    if site_config is not None:
        # Step 2: Remove plugins in site_config.disabled
        site_disabled = set(site_config.get("disabled", []))
        enabled -= site_disabled

        # Step 3: Remove plugins in PIPELINE_DISABLED_PLUGINS env var
        enabled -= set(disabled_env)

        # Step 4: Add plugins in site_config.enabled
        site_enabled = set(site_config.get("enabled", []))
        enabled |= site_enabled
    else:
        # When site_config is NULL, use global config minus PIPELINE_DISABLED_PLUGINS
        enabled -= set(disabled_env)

    # Merge params: site_config.params overrides (only when site_config is present)
    merged_params: dict[str, dict] = {}
    if site_config is not None:
        merged_params = {
            k: dict(v) for k, v in site_config.get("params", {}).items()
        }

    return enabled, merged_params

