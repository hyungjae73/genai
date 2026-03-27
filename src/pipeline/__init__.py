"""
Crawl Pipeline Architecture.

4ステージ構成のパイプラインフレームワーク:
  Stage 1: PageFetcher
  Stage 2: DataExtractor
  Stage 3: Validator
  Stage 4: Reporter
"""

from src.pipeline.browser_pool import BrowserPool
from src.pipeline.context import CrawlContext, VariantCapture
from src.pipeline.pipeline import CrawlPipeline
from src.pipeline.plugin import CrawlPlugin

__all__ = ["BrowserPool", "CrawlContext", "CrawlPipeline", "CrawlPlugin", "VariantCapture"]
