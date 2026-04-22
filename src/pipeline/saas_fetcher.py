"""
SaaSFetcher — SaaS API-based PageFetcher implementation.

Delegates page fetching to external scraping services (ZenRows, ScraperAPI)
via httpx HTTP GET requests.

Requirements: 10.3, 12.1, 12.2, 12.4, 12.5
"""

from __future__ import annotations

import logging

import httpx

from src.core.retry import with_retry
from src.models import MonitoringSite
from src.pipeline.fetcher_protocol import FetchResult

logger = logging.getLogger(__name__)

# Provider endpoint templates
PROVIDER_ENDPOINTS = {
    "zenrows": "https://api.zenrows.com/v1/",
    "scraperapi": "https://api.scraperapi.com/",
}


def _is_retryable_http_error(exc: Exception) -> bool:
    """Determine if an HTTP error is retryable.

    Only retry on HTTP 5xx server errors. Not on 4xx client errors.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


class SaaSFetcher:
    """SaaS API ベースの PageFetcher 実装。

    ZenRows または ScraperAPI にリクエストを委譲する。
    """

    def __init__(
        self,
        api_key: str,
        provider: str = "zenrows",
        timeout: float = 60.0,
    ) -> None:
        self._api_key = api_key
        self._provider = provider
        self._timeout = timeout
        self._endpoint = PROVIDER_ENDPOINTS[provider]

    async def fetch(self, url: str, site: MonitoringSite) -> FetchResult:
        """SaaS API 経由でページを取得する。

        Retries on transient errors: ConnectError, TimeoutException, HTTP 5xx.
        Does NOT retry on 4xx client errors.
        """
        params = self._build_params(url)

        @with_retry(
            retry_on=(httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError),
            retry_if=_is_retryable_http_error,
            max_attempts=3,
        )
        async def _do_fetch():
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(self._endpoint, params=params)
                response.raise_for_status()
                return FetchResult(
                    html=response.text,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                )

        return await _do_fetch()

    def _build_params(self, url: str) -> dict[str, str]:
        """プロバイダ固有のリクエストパラメータを構築する。"""
        if self._provider == "zenrows":
            return {"apikey": self._api_key, "url": url, "js_render": "true"}
        elif self._provider == "scraperapi":
            return {"api_key": self._api_key, "url": url, "render": "true"}
        raise ValueError(f"Unknown provider: {self._provider}")
