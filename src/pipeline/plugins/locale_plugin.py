"""
LocalePlugin — PageFetcher ステージ プラグイン。

ブラウザコンテキスト作成時に使用するロケール設定を ctx.metadata に格納する。
PageFetcher ステージがブラウザページを生成する際にこの設定を参照する。

Requirements: 3.1, 3.2, 3.3, 3.4
"""

from __future__ import annotations

from src.pipeline.context import CrawlContext
from src.pipeline.plugin import CrawlPlugin


class LocalePlugin(CrawlPlugin):
    """ブラウザのロケール・ヘッダー・ビューポートを設定するプラグイン。

    ctx.metadata に以下のキーで設定を格納する:
      - locale_config: ブラウザコンテキスト生成時に使用する設定 dict

    PageFetcher ステージはこの設定を参照してブラウザページを生成する。
    """

    LOCALE = "ja-JP"
    ACCEPT_LANGUAGE = "ja-JP,ja;q=0.9"
    VIEWPORT_WIDTH = 1920
    VIEWPORT_HEIGHT = 1080
    DEVICE_SCALE_FACTOR = 2

    async def execute(self, ctx: CrawlContext) -> CrawlContext:
        """ロケール設定を ctx.metadata に格納する。

        Args:
            ctx: パイプライン共有コンテキスト

        Returns:
            locale_config を metadata に追記した CrawlContext
        """
        ctx.metadata["locale_config"] = {
            "locale": self.LOCALE,
            "extra_http_headers": {"Accept-Language": self.ACCEPT_LANGUAGE},
            "viewport": {
                "width": self.VIEWPORT_WIDTH,
                "height": self.VIEWPORT_HEIGHT,
            },
            "device_scale_factor": self.DEVICE_SCALE_FACTOR,
        }
        return ctx

    def should_run(self, ctx: CrawlContext) -> bool:
        """常に True を返す。"""
        return True
