"""
PageFetcher Protocol — abstract interface for page fetching.

Defines a structural subtyping protocol that abstracts both Playwright-based
and SaaS API-based page fetching behind a unified interface.

Requirements: 10.1, 10.4
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from src.models import MonitoringSite


@dataclass
class FetchResult:
    """フェッチ結果。"""

    html: str
    status_code: int
    headers: dict[str, str]


@runtime_checkable
class PageFetcher(Protocol):
    """ページ取得の抽象インターフェース（構造的部分型）。"""

    async def fetch(self, url: str, site: MonitoringSite) -> FetchResult:
        """URL からページを取得する。"""
        ...
