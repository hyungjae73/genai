"""
Scraping configuration — anti-bot stealth settings and proxy-ready architecture.

All scraping-related settings are centralized here via pydantic-settings.
Sensitive values (proxy credentials) use SecretStr for automatic log masking.
"""

from __future__ import annotations

import random
from typing import Optional

from pydantic import SecretStr
from pydantic_settings import BaseSettings

# Fixed User-Agent: latest Windows Chrome (single consistent fingerprint)
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

# Viewport pool for randomization
VIEWPORT_POOL: list[dict[str, int]] = [
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1440, "height": 900},
    {"width": 1536, "height": 864},
]


class ScrapingConfig(BaseSettings):
    """Centralized scraping configuration loaded from environment variables.

    Proxy fields are Optional — when None, Playwright connects directly.
    """

    # Anti-bot fingerprint
    scraping_user_agent: str = DEFAULT_USER_AGENT

    # Proxy (Residential Proxy ready — Bright Data, ScraperAPI, etc.)
    scraping_proxy_url: Optional[str] = None
    scraping_proxy_username: Optional[str] = None
    scraping_proxy_password: Optional[SecretStr] = None

    # Delay jitter range (seconds)
    scraping_jitter_min: float = 0.8
    scraping_jitter_max: float = 2.5

    # Stealth toggle (disable for debugging)
    scraping_stealth_enabled: bool = True

    # Phase 2.5: VLM (Vision-Language Model) settings
    vlm_api_key: Optional[SecretStr] = None
    vlm_provider: str = "gemini"
    vlm_rate_limit_per_site_hour: int = 5
    antibot_signatures_json: Optional[str] = None

    # Phase 3: SaaS API settings
    saas_api_key: Optional[SecretStr] = None
    saas_provider: str = "zenrows"

    # Phase 4: Adaptive evasion settings
    adaptive_success_threshold: float = 0.8
    adaptive_epsilon: float = 0.2
    adaptive_min_trials: int = 20

    model_config = {"env_prefix": "", "env_file": ".env", "extra": "ignore"}

    def get_random_viewport(self) -> dict[str, int]:
        """Return a randomly selected viewport from the pool."""
        return random.choice(VIEWPORT_POOL)

    def get_proxy_dict(self) -> Optional[dict[str, str]]:
        """Build Playwright proxy dict if proxy is configured, else None."""
        if not self.scraping_proxy_url:
            return None
        proxy: dict[str, str] = {"server": self.scraping_proxy_url}
        if self.scraping_proxy_username:
            proxy["username"] = self.scraping_proxy_username
        if self.scraping_proxy_password:
            proxy["password"] = self.scraping_proxy_password.get_secret_value()
        return proxy

    def get_jitter(self) -> float:
        """Return a random jitter delay in seconds."""
        return random.uniform(self.scraping_jitter_min, self.scraping_jitter_max)


# Module-level singleton (import and use directly)
scraping_config = ScrapingConfig()
