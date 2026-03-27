"""
CrawlPlugin 抽象基底クラス。

全パイプラインプラグインの抽象基底クラスを定義する。
各プラグインは execute(ctx) と should_run(ctx) を実装する必要がある。

Requirements: 1.1, 1.2
"""

from abc import ABC, abstractmethod

from src.pipeline.context import CrawlContext


class CrawlPlugin(ABC):
    """全プラグインの抽象基底クラス。

    各プラグインはこのクラスを継承し、execute() と should_run() を実装する。
    execute() は CrawlContext を受け取り、処理結果を追記して返却する。
    should_run() は実行条件を判定し、False の場合はパイプラインからスキップされる。
    """

    @abstractmethod
    async def execute(self, ctx: CrawlContext) -> CrawlContext:
        """プラグイン処理を実行し、結果を追記した CrawlContext を返却する。

        Args:
            ctx: パイプライン共有コンテキスト

        Returns:
            処理結果を追記した CrawlContext
        """
        ...

    @abstractmethod
    def should_run(self, ctx: CrawlContext) -> bool:
        """実行条件を判定する。False の場合スキップされる。

        Args:
            ctx: パイプライン共有コンテキスト

        Returns:
            True の場合 execute() が呼び出される
        """
        ...

    @property
    def name(self) -> str:
        """プラグイン名を返す。クラス名をそのまま使用する。"""
        return self.__class__.__name__
