"""
Unit tests for Stealth Browser Hardening — Phase 1 existing code.

Feature: stealth-browser-hardening
Covers: StealthBrowserFactory context creation, stealth toggle, proxy passthrough,
        ScrapingConfig settings loading and singleton.

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 4.3

All Playwright objects are mocked since Playwright may not be installed
in the test environment.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

from src.scraping_config import (
    DEFAULT_USER_AGENT,
    VIEWPORT_POOL,
    ScrapingConfig,
)
from src.pipeline.stealth_browser import StealthBrowserFactory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_browser():
    """Create a mock Playwright Browser."""
    browser = MagicMock()
    mock_context = AsyncMock()
    browser.new_context = AsyncMock(return_value=mock_context)
    return browser


def _make_mock_playwright():
    """Create a mock Playwright instance."""
    pw = MagicMock()
    mock_browser = AsyncMock()
    pw.chromium.launch = AsyncMock(return_value=mock_browser)
    return pw


# ---------------------------------------------------------------------------
# Requirement 1.1 — StealthBrowserFactory is single entry point
# ---------------------------------------------------------------------------


class TestStealthBrowserFactorySingleEntryPoint:
    """Validates: Requirement 1.1 — StealthBrowserFactory serves as single entry point."""

    def test_factory_instantiates_with_default_config(self):
        """Factory can be created without arguments, using the module singleton."""
        factory = StealthBrowserFactory()
        assert factory._config is not None

    def test_factory_accepts_custom_config(self):
        """Factory accepts an injected ScrapingConfig."""
        config = ScrapingConfig(scraping_user_agent="CustomUA/1.0")
        factory = StealthBrowserFactory(config=config)
        assert factory._config is config

    def test_factory_exposes_create_browser(self):
        """Factory has create_browser method."""
        factory = StealthBrowserFactory()
        assert callable(factory.create_browser)

    def test_factory_exposes_create_context(self):
        """Factory has create_context method."""
        factory = StealthBrowserFactory()
        assert callable(factory.create_context)

    def test_factory_exposes_apply_stealth(self):
        """Factory has apply_stealth method."""
        factory = StealthBrowserFactory()
        assert callable(factory.apply_stealth)

    def test_factory_exposes_create_page(self):
        """Factory has create_page convenience method."""
        factory = StealthBrowserFactory()
        assert callable(factory.create_page)


# ---------------------------------------------------------------------------
# Requirement 1.2 — create_context sets correct User-Agent
# ---------------------------------------------------------------------------


class TestCreateContextUserAgent:
    """Validates: Requirement 1.2 — User-Agent set to fixed Chrome string."""

    @pytest.mark.asyncio
    async def test_context_uses_default_user_agent(self):
        """create_context sets the default Chrome UA when no custom UA configured."""
        factory = StealthBrowserFactory()
        mock_browser = _make_mock_browser()

        await factory.create_context(mock_browser)

        mock_browser.new_context.assert_called_once()
        call_kwargs = mock_browser.new_context.call_args[1]
        assert call_kwargs["user_agent"] == DEFAULT_USER_AGENT

    @pytest.mark.asyncio
    async def test_context_uses_custom_user_agent(self):
        """create_context uses the UA from a custom ScrapingConfig."""
        custom_ua = "MyBot/2.0"
        config = ScrapingConfig(scraping_user_agent=custom_ua)
        factory = StealthBrowserFactory(config=config)
        mock_browser = _make_mock_browser()

        await factory.create_context(mock_browser)

        call_kwargs = mock_browser.new_context.call_args[1]
        assert call_kwargs["user_agent"] == custom_ua


# ---------------------------------------------------------------------------
# Requirement 1.3 — create_context selects viewport from VIEWPORT_POOL
# ---------------------------------------------------------------------------


class TestCreateContextViewport:
    """Validates: Requirement 1.3 — viewport randomly selected from pool."""

    @pytest.mark.asyncio
    async def test_context_viewport_from_pool(self):
        """create_context selects a viewport that is in VIEWPORT_POOL."""
        factory = StealthBrowserFactory()
        mock_browser = _make_mock_browser()

        await factory.create_context(mock_browser)

        call_kwargs = mock_browser.new_context.call_args[1]
        assert call_kwargs["viewport"] in VIEWPORT_POOL

    @pytest.mark.asyncio
    async def test_context_accepts_viewport_override(self):
        """create_context uses an explicit viewport when provided."""
        custom_vp = {"width": 800, "height": 600}
        factory = StealthBrowserFactory()
        mock_browser = _make_mock_browser()

        await factory.create_context(mock_browser, viewport=custom_vp)

        call_kwargs = mock_browser.new_context.call_args[1]
        assert call_kwargs["viewport"] == custom_vp


# ---------------------------------------------------------------------------
# Requirement 1.4 — apply_stealth calls playwright_stealth when enabled
# ---------------------------------------------------------------------------


class TestApplyStealthEnabled:
    """Validates: Requirement 1.4 — stealth patches applied via playwright-stealth."""

    @pytest.mark.asyncio
    async def test_apply_stealth_calls_stealth_async(self):
        """apply_stealth invokes stealth_async when stealth is enabled."""
        config = ScrapingConfig(scraping_stealth_enabled=True)
        factory = StealthBrowserFactory(config=config)
        mock_page = AsyncMock()

        with patch(
            "src.pipeline.stealth_browser.stealth_async",
            new_callable=AsyncMock,
            create=True,
        ) as mock_stealth:
            # Patch the import inside apply_stealth
            with patch.dict(
                "sys.modules",
                {"playwright_stealth": MagicMock(stealth_async=mock_stealth)},
            ):
                await factory.apply_stealth(mock_page)
                mock_stealth.assert_called_once_with(mock_page)


# ---------------------------------------------------------------------------
# Requirement 1.5 — apply_stealth logs warning when not installed
# ---------------------------------------------------------------------------


class TestApplyStealthNotInstalled:
    """Validates: Requirement 1.5 — warning logged when playwright-stealth missing."""

    @pytest.mark.asyncio
    async def test_apply_stealth_logs_warning_on_import_error(self):
        """apply_stealth logs a warning and continues when playwright-stealth is missing."""
        config = ScrapingConfig(scraping_stealth_enabled=True)
        factory = StealthBrowserFactory(config=config)
        mock_page = AsyncMock()

        with patch(
            "builtins.__import__",
            side_effect=_import_error_for_stealth,
        ):
            with patch("src.pipeline.stealth_browser.logger") as mock_logger:
                await factory.apply_stealth(mock_page)
                mock_logger.warning.assert_called_once()
                assert "playwright-stealth not installed" in mock_logger.warning.call_args[0][0]


def _import_error_for_stealth(name, *args, **kwargs):
    """Raise ImportError only for playwright_stealth."""
    if name == "playwright_stealth":
        raise ImportError("No module named 'playwright_stealth'")
    return original_import(name, *args, **kwargs)


import builtins
original_import = builtins.__import__


# ---------------------------------------------------------------------------
# Requirement 1.6 — apply_stealth skips when disabled
# ---------------------------------------------------------------------------


class TestApplyStealthDisabled:
    """Validates: Requirement 1.6 — stealth skipped when scraping_stealth_enabled=False."""

    @pytest.mark.asyncio
    async def test_apply_stealth_skips_when_disabled(self):
        """apply_stealth returns immediately without calling stealth_async."""
        config = ScrapingConfig(scraping_stealth_enabled=False)
        factory = StealthBrowserFactory(config=config)
        mock_page = AsyncMock()

        with patch.dict("sys.modules", {"playwright_stealth": MagicMock()}) as mods:
            await factory.apply_stealth(mock_page)
            # stealth_async should never be called
            stealth_mod = mods.get("playwright_stealth")
            if stealth_mod and hasattr(stealth_mod, "stealth_async"):
                stealth_mod.stealth_async.assert_not_called()


# ---------------------------------------------------------------------------
# Requirement 3.1 — ScrapingConfig loads proxy settings
# ---------------------------------------------------------------------------


class TestScrapingConfigProxy:
    """Validates: Requirement 3.1 — proxy settings loaded from env vars."""

    def test_proxy_fields_default_to_none(self):
        """Proxy fields are None by default."""
        config = ScrapingConfig()
        assert config.scraping_proxy_url is None
        assert config.scraping_proxy_username is None
        assert config.scraping_proxy_password is None

    def test_proxy_fields_loaded(self):
        """Proxy fields can be set explicitly."""
        config = ScrapingConfig(
            scraping_proxy_url="http://proxy.example.com:8080",
            scraping_proxy_username="user1",
            scraping_proxy_password="secret123",
        )
        assert config.scraping_proxy_url == "http://proxy.example.com:8080"
        assert config.scraping_proxy_username == "user1"
        assert config.scraping_proxy_password.get_secret_value() == "secret123"

    def test_get_proxy_dict_with_full_config(self):
        """get_proxy_dict returns server, username, password when all set."""
        config = ScrapingConfig(
            scraping_proxy_url="http://proxy.example.com:8080",
            scraping_proxy_username="user1",
            scraping_proxy_password="secret123",
        )
        proxy = config.get_proxy_dict()
        assert proxy == {
            "server": "http://proxy.example.com:8080",
            "username": "user1",
            "password": "secret123",
        }

    def test_get_proxy_dict_without_credentials(self):
        """get_proxy_dict returns only server when no credentials set."""
        config = ScrapingConfig(scraping_proxy_url="http://proxy.example.com:8080")
        proxy = config.get_proxy_dict()
        assert proxy == {"server": "http://proxy.example.com:8080"}
        assert "username" not in proxy
        assert "password" not in proxy


# ---------------------------------------------------------------------------
# Requirement 3.2 — SecretStr for proxy password
# ---------------------------------------------------------------------------


class TestScrapingConfigSecretStr:
    """Validates: Requirement 3.2 — proxy password uses SecretStr."""

    def test_proxy_password_is_secret_str(self):
        """scraping_proxy_password is stored as SecretStr."""
        config = ScrapingConfig(scraping_proxy_password="my_secret")
        assert isinstance(config.scraping_proxy_password, SecretStr)

    def test_proxy_password_hidden_in_repr(self):
        """SecretStr hides the password in string representation."""
        config = ScrapingConfig(scraping_proxy_password="my_secret")
        repr_str = repr(config.scraping_proxy_password)
        assert "my_secret" not in repr_str

    def test_proxy_password_accessible_via_get_secret_value(self):
        """The actual password is accessible via get_secret_value()."""
        config = ScrapingConfig(scraping_proxy_password="my_secret")
        assert config.scraping_proxy_password.get_secret_value() == "my_secret"


# ---------------------------------------------------------------------------
# Requirement 3.3 — create_browser passes proxy when configured
# ---------------------------------------------------------------------------


class TestCreateBrowserProxy:
    """Validates: Requirement 3.3 — proxy passed to Playwright launch."""

    @pytest.mark.asyncio
    async def test_create_browser_with_proxy(self):
        """create_browser includes proxy in launch kwargs when configured."""
        config = ScrapingConfig(
            scraping_proxy_url="http://proxy.example.com:8080",
            scraping_proxy_username="user1",
            scraping_proxy_password="pass1",
        )
        factory = StealthBrowserFactory(config=config)
        mock_pw = _make_mock_playwright()

        await factory.create_browser(playwright=mock_pw)

        call_kwargs = mock_pw.chromium.launch.call_args[1]
        assert "proxy" in call_kwargs
        assert call_kwargs["proxy"]["server"] == "http://proxy.example.com:8080"
        assert call_kwargs["proxy"]["username"] == "user1"
        assert call_kwargs["proxy"]["password"] == "pass1"


# ---------------------------------------------------------------------------
# Requirement 3.4 — create_browser launches direct when no proxy
# ---------------------------------------------------------------------------


class TestCreateBrowserDirect:
    """Validates: Requirement 3.4 — direct connection when no proxy."""

    @pytest.mark.asyncio
    async def test_create_browser_without_proxy(self):
        """create_browser launches without proxy when none configured."""
        config = ScrapingConfig(scraping_proxy_url=None)
        factory = StealthBrowserFactory(config=config)
        mock_pw = _make_mock_playwright()

        await factory.create_browser(playwright=mock_pw)

        call_kwargs = mock_pw.chromium.launch.call_args[1]
        assert "proxy" not in call_kwargs
        assert call_kwargs["headless"] is True

    @pytest.mark.asyncio
    async def test_create_browser_raises_without_playwright(self):
        """create_browser raises RuntimeError when no Playwright instance available."""
        factory = StealthBrowserFactory()
        with pytest.raises(RuntimeError, match="No Playwright instance"):
            await factory.create_browser()


# ---------------------------------------------------------------------------
# Requirement 4.1 — ScrapingConfig centralizes all settings
# ---------------------------------------------------------------------------


class TestScrapingConfigCentralized:
    """Validates: Requirement 4.1 — all scraping settings in one BaseSettings class."""

    def test_has_user_agent(self):
        config = ScrapingConfig()
        assert hasattr(config, "scraping_user_agent")
        assert config.scraping_user_agent == DEFAULT_USER_AGENT

    def test_has_proxy_settings(self):
        config = ScrapingConfig()
        assert hasattr(config, "scraping_proxy_url")
        assert hasattr(config, "scraping_proxy_username")
        assert hasattr(config, "scraping_proxy_password")

    def test_has_jitter_settings(self):
        config = ScrapingConfig()
        assert hasattr(config, "scraping_jitter_min")
        assert hasattr(config, "scraping_jitter_max")
        assert config.scraping_jitter_min == 0.8
        assert config.scraping_jitter_max == 2.5

    def test_has_stealth_toggle(self):
        config = ScrapingConfig()
        assert hasattr(config, "scraping_stealth_enabled")
        assert config.scraping_stealth_enabled is True


# ---------------------------------------------------------------------------
# Requirement 4.2 — Module-level singleton
# ---------------------------------------------------------------------------


class TestScrapingConfigSingleton:
    """Validates: Requirement 4.2 — module-level singleton for direct import."""

    def test_module_singleton_exists(self):
        """scraping_config is importable as a module-level singleton."""
        from src.scraping_config import scraping_config

        assert isinstance(scraping_config, ScrapingConfig)

    def test_factory_uses_singleton_by_default(self):
        """StealthBrowserFactory uses the module singleton when no config passed."""
        from src.scraping_config import scraping_config

        factory = StealthBrowserFactory()
        assert factory._config is scraping_config


# ---------------------------------------------------------------------------
# Requirement 4.3 — ScrapingConfig loads from env vars
# ---------------------------------------------------------------------------


class TestScrapingConfigEnvVars:
    """Validates: Requirement 4.3 — settings loaded from environment variables."""

    def test_loads_user_agent_from_env(self, monkeypatch):
        """SCRAPING_USER_AGENT env var overrides default."""
        monkeypatch.setenv("SCRAPING_USER_AGENT", "EnvBot/1.0")
        config = ScrapingConfig()
        assert config.scraping_user_agent == "EnvBot/1.0"

    def test_loads_proxy_url_from_env(self, monkeypatch):
        """SCRAPING_PROXY_URL env var sets proxy."""
        monkeypatch.setenv("SCRAPING_PROXY_URL", "http://env-proxy:9090")
        config = ScrapingConfig()
        assert config.scraping_proxy_url == "http://env-proxy:9090"

    def test_loads_stealth_enabled_from_env(self, monkeypatch):
        """SCRAPING_STEALTH_ENABLED env var toggles stealth."""
        monkeypatch.setenv("SCRAPING_STEALTH_ENABLED", "false")
        config = ScrapingConfig()
        assert config.scraping_stealth_enabled is False

    def test_loads_jitter_from_env(self, monkeypatch):
        """SCRAPING_JITTER_MIN and SCRAPING_JITTER_MAX env vars set jitter range."""
        monkeypatch.setenv("SCRAPING_JITTER_MIN", "1.5")
        monkeypatch.setenv("SCRAPING_JITTER_MAX", "5.0")
        config = ScrapingConfig()
        assert config.scraping_jitter_min == 1.5
        assert config.scraping_jitter_max == 5.0


# ---------------------------------------------------------------------------
# Requirement 15.5, 16.4 — Phase 2.5 VLM config fields
# ---------------------------------------------------------------------------


class TestScrapingConfigVLMFields:
    """Validates: Requirements 15.5, 16.4 — VLM config fields in ScrapingConfig."""

    def test_vlm_api_key_defaults_to_none(self):
        config = ScrapingConfig()
        assert config.vlm_api_key is None

    def test_vlm_api_key_is_secret_str(self):
        config = ScrapingConfig(vlm_api_key="test-vlm-key")
        assert isinstance(config.vlm_api_key, SecretStr)
        assert config.vlm_api_key.get_secret_value() == "test-vlm-key"

    def test_vlm_provider_defaults_to_gemini(self):
        config = ScrapingConfig()
        assert config.vlm_provider == "gemini"

    def test_vlm_provider_can_be_set(self):
        config = ScrapingConfig(vlm_provider="claude")
        assert config.vlm_provider == "claude"

    def test_vlm_rate_limit_defaults_to_5(self):
        config = ScrapingConfig()
        assert config.vlm_rate_limit_per_site_hour == 5

    def test_antibot_signatures_json_defaults_to_none(self):
        config = ScrapingConfig()
        assert config.antibot_signatures_json is None

    def test_antibot_signatures_json_can_be_set(self):
        sigs = '[{"name": "test", "type": "css"}]'
        config = ScrapingConfig(antibot_signatures_json=sigs)
        assert config.antibot_signatures_json == sigs

    def test_vlm_fields_from_env(self, monkeypatch):
        monkeypatch.setenv("VLM_API_KEY", "env-vlm-key")
        monkeypatch.setenv("VLM_PROVIDER", "claude")
        monkeypatch.setenv("VLM_RATE_LIMIT_PER_SITE_HOUR", "10")
        monkeypatch.setenv("ANTIBOT_SIGNATURES_JSON", '[]')
        config = ScrapingConfig()
        assert config.vlm_api_key.get_secret_value() == "env-vlm-key"
        assert config.vlm_provider == "claude"
        assert config.vlm_rate_limit_per_site_hour == 10
        assert config.antibot_signatures_json == "[]"


# ---------------------------------------------------------------------------
# Requirement 12.3 — Phase 3 SaaS API config fields
# ---------------------------------------------------------------------------


class TestScrapingConfigSaaSFields:
    """Validates: Requirement 12.3 — SaaS API config fields in ScrapingConfig."""

    def test_saas_api_key_defaults_to_none(self):
        config = ScrapingConfig()
        assert config.saas_api_key is None

    def test_saas_api_key_is_secret_str(self):
        config = ScrapingConfig(saas_api_key="test-saas-key")
        assert isinstance(config.saas_api_key, SecretStr)
        assert config.saas_api_key.get_secret_value() == "test-saas-key"

    def test_saas_provider_defaults_to_zenrows(self):
        config = ScrapingConfig()
        assert config.saas_provider == "zenrows"

    def test_saas_provider_can_be_set(self):
        config = ScrapingConfig(saas_provider="scraperapi")
        assert config.saas_provider == "scraperapi"

    def test_saas_fields_from_env(self, monkeypatch):
        monkeypatch.setenv("SAAS_API_KEY", "env-saas-key")
        monkeypatch.setenv("SAAS_PROVIDER", "scraperapi")
        config = ScrapingConfig()
        assert config.saas_api_key.get_secret_value() == "env-saas-key"
        assert config.saas_provider == "scraperapi"


# ---------------------------------------------------------------------------
# Requirement 17.4, 18.2, 18.4 — Phase 4 Adaptive evasion config fields
# ---------------------------------------------------------------------------


class TestScrapingConfigAdaptiveFields:
    """Validates: Requirements 17.4, 18.2, 18.4 — Adaptive evasion config fields."""

    def test_adaptive_success_threshold_defaults_to_0_8(self):
        config = ScrapingConfig()
        assert config.adaptive_success_threshold == 0.8

    def test_adaptive_epsilon_defaults_to_0_2(self):
        config = ScrapingConfig()
        assert config.adaptive_epsilon == 0.2

    def test_adaptive_min_trials_defaults_to_20(self):
        config = ScrapingConfig()
        assert config.adaptive_min_trials == 20

    def test_adaptive_fields_can_be_set(self):
        config = ScrapingConfig(
            adaptive_success_threshold=0.9,
            adaptive_epsilon=0.1,
            adaptive_min_trials=50,
        )
        assert config.adaptive_success_threshold == 0.9
        assert config.adaptive_epsilon == 0.1
        assert config.adaptive_min_trials == 50

    def test_adaptive_fields_from_env(self, monkeypatch):
        monkeypatch.setenv("ADAPTIVE_SUCCESS_THRESHOLD", "0.7")
        monkeypatch.setenv("ADAPTIVE_EPSILON", "0.3")
        monkeypatch.setenv("ADAPTIVE_MIN_TRIALS", "30")
        config = ScrapingConfig()
        assert config.adaptive_success_threshold == 0.7
        assert config.adaptive_epsilon == 0.3
        assert config.adaptive_min_trials == 30
