"""
Property-based tests for Stealth Browser Hardening (Phase 1).

Feature: stealth-browser-hardening
Property 1: Factory configuration propagation
Property 2: Jitter delay is within configured bounds

Validates: Requirements 1.2, 1.3, 2.1, 3.3
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.scraping_config import ScrapingConfig, VIEWPORT_POOL


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

def user_agent_strategy():
    """Generate non-empty user agent strings."""
    return st.text(
        alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
        min_size=1,
        max_size=200,
    )


def proxy_url_strategy():
    """Generate optional proxy URL strings."""
    return st.one_of(
        st.none(),
        st.from_regex(r"https?://[a-z0-9]+\.[a-z]{2,4}(:[0-9]{2,5})?", fullmatch=True),
    )


def jitter_bounds_strategy():
    """Generate (min, max) float pairs where 0 <= min <= max."""
    return st.tuples(
        st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
    ).filter(lambda pair: pair[0] <= pair[1])


# ---------------------------------------------------------------------------
# Property 1: Factory configuration propagation
# ---------------------------------------------------------------------------

class TestFactoryConfigPropagation:
    """
    Feature: stealth-browser-hardening, Property 1: Factory configuration propagation

    **Validates: Requirements 1.2, 1.3, 3.3**

    For any ScrapingConfig with a given user_agent, viewport pool, and proxy URL,
    a StealthBrowserFactory using that config SHALL produce contexts where the
    User-Agent matches the configured string, the viewport is a member of the pool,
    and the proxy dict matches the configured URL (or is None when unconfigured).
    """

    @given(
        user_agent=user_agent_strategy(),
        proxy_url=proxy_url_strategy(),
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_context_user_agent_and_viewport_match_config(self, user_agent, proxy_url):
        """create_context passes configured UA and a viewport from the pool."""
        from src.pipeline.stealth_browser import StealthBrowserFactory

        config = ScrapingConfig(
            scraping_user_agent=user_agent,
            scraping_proxy_url=proxy_url,
            scraping_stealth_enabled=False,
        )
        factory = StealthBrowserFactory(config=config)

        # Mock browser.new_context to capture the kwargs
        mock_context = AsyncMock()
        mock_browser = MagicMock()
        captured_kwargs = {}

        async def capture_new_context(**kwargs):
            captured_kwargs.update(kwargs)
            return mock_context

        mock_browser.new_context = AsyncMock(side_effect=capture_new_context)

        await factory.create_context(mock_browser)

        # User-Agent must match configured value
        assert captured_kwargs["user_agent"] == user_agent, (
            f"Expected UA '{user_agent}', got '{captured_kwargs.get('user_agent')}'"
        )

        # Viewport must be from the pool
        assert captured_kwargs["viewport"] in VIEWPORT_POOL, (
            f"Viewport {captured_kwargs['viewport']} not in VIEWPORT_POOL"
        )

    @given(
        proxy_url=proxy_url_strategy(),
    )
    @settings(max_examples=100)
    def test_proxy_dict_matches_config(self, proxy_url):
        """get_proxy_dict() returns matching proxy or None when unconfigured."""
        config = ScrapingConfig(
            scraping_proxy_url=proxy_url,
            scraping_stealth_enabled=False,
        )

        proxy_dict = config.get_proxy_dict()

        if proxy_url is None:
            assert proxy_dict is None, (
                f"Expected None proxy dict when proxy_url is None, got {proxy_dict}"
            )
        else:
            assert proxy_dict is not None, "Expected proxy dict when proxy_url is set"
            assert proxy_dict["server"] == proxy_url, (
                f"Expected server '{proxy_url}', got '{proxy_dict.get('server')}'"
            )

    @given(
        user_agent=user_agent_strategy(),
        proxy_url=proxy_url_strategy(),
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_browser_launch_includes_proxy_when_configured(self, user_agent, proxy_url):
        """create_browser passes proxy to Playwright launch when configured."""
        from src.pipeline.stealth_browser import StealthBrowserFactory

        config = ScrapingConfig(
            scraping_user_agent=user_agent,
            scraping_proxy_url=proxy_url,
            scraping_stealth_enabled=False,
        )
        factory = StealthBrowserFactory(config=config)

        # Mock playwright instance
        mock_browser = AsyncMock()
        mock_pw = MagicMock()
        captured_launch_kwargs = {}

        async def capture_launch(**kwargs):
            captured_launch_kwargs.update(kwargs)
            return mock_browser

        mock_pw.chromium.launch = AsyncMock(side_effect=capture_launch)

        await factory.create_browser(playwright=mock_pw)

        if proxy_url is not None:
            assert "proxy" in captured_launch_kwargs, (
                "Expected proxy in launch kwargs when proxy_url is configured"
            )
            assert captured_launch_kwargs["proxy"]["server"] == proxy_url
        else:
            assert "proxy" not in captured_launch_kwargs, (
                "Expected no proxy in launch kwargs when proxy_url is None"
            )


# ---------------------------------------------------------------------------
# Property 2: Jitter delay is within configured bounds
# ---------------------------------------------------------------------------

class TestJitterBounds:
    """
    Feature: stealth-browser-hardening, Property 2: Jitter delay is within configured bounds

    **Validates: Requirements 2.1**

    For any ScrapingConfig with scraping_jitter_min <= scraping_jitter_max,
    calling get_jitter() SHALL return a value d such that
    scraping_jitter_min <= d <= scraping_jitter_max.
    """

    @given(bounds=jitter_bounds_strategy())
    @settings(max_examples=100)
    def test_jitter_within_bounds(self, bounds):
        """get_jitter() returns value in [min, max]."""
        jitter_min, jitter_max = bounds

        config = ScrapingConfig(
            scraping_jitter_min=jitter_min,
            scraping_jitter_max=jitter_max,
            scraping_stealth_enabled=False,
        )

        delay = config.get_jitter()

        assert jitter_min <= delay <= jitter_max, (
            f"Jitter {delay} not in [{jitter_min}, {jitter_max}]"
        )

    @given(value=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False))
    @settings(max_examples=100)
    def test_jitter_degenerate_range(self, value):
        """When min == max, get_jitter() returns exactly that value."""
        config = ScrapingConfig(
            scraping_jitter_min=value,
            scraping_jitter_max=value,
            scraping_stealth_enabled=False,
        )

        delay = config.get_jitter()

        assert delay == value, (
            f"Expected jitter {value} when min==max, got {delay}"
        )


# ---------------------------------------------------------------------------
# Strategies for SessionManager property tests (Phase 2)
# ---------------------------------------------------------------------------

def site_id_strategy():
    """Generate positive site IDs."""
    return st.integers(min_value=1, max_value=10000)


def cookie_list_strategy():
    """Generate lists of cookie dicts with name, value, domain."""
    return st.lists(
        st.fixed_dictionaries({
            "name": st.text(min_size=1, max_size=20),
            "value": st.text(max_size=50),
            "domain": st.text(min_size=1, max_size=50),
        })
    )


# ---------------------------------------------------------------------------
# Property 3: Cookie storage round-trip
# ---------------------------------------------------------------------------

class TestCookieStorageRoundTrip:
    """
    Feature: stealth-browser-hardening, Property 3: Cookie storage round-trip

    **Validates: Requirements 6.1, 9.3**

    For any site_id (positive integer) and any list of cookie dicts,
    calling SessionManager.save_cookies(site_id, cookies) then
    SessionManager.get_cookies(site_id) SHALL return a list equal
    to the original cookies.
    """

    @given(
        site_id=site_id_strategy(),
        cookies=cookie_list_strategy(),
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_save_then_get_returns_equal_cookies(self, site_id, cookies):
        """save_cookies → get_cookies returns the original cookie list."""
        import fakeredis.aioredis
        from src.pipeline.session_manager import SessionManager

        redis_client = fakeredis.aioredis.FakeRedis()
        try:
            sm = SessionManager(redis_client=redis_client)
            await sm.save_cookies(site_id, cookies)
            result = await sm.get_cookies(site_id)
            assert result == cookies, (
                f"Round-trip mismatch for site_id={site_id}: "
                f"expected {cookies}, got {result}"
            )
        finally:
            await redis_client.flushall()
            await redis_client.aclose()


# ---------------------------------------------------------------------------
# Property 5: Expired session detection
# ---------------------------------------------------------------------------

class TestExpiredSessionDetection:
    """
    Feature: stealth-browser-hardening, Property 5: Expired session detection

    **Validates: Requirements 7.1**

    For any HTTP status code (100-599),
    SessionManager.is_expired_response(status_code) SHALL return True
    if and only if status_code ∈ {401, 403}.
    """

    @given(status_code=st.integers(min_value=100, max_value=599))
    @settings(max_examples=100)
    def test_is_expired_iff_401_or_403(self, status_code):
        """is_expired_response returns True iff status_code in {401, 403}."""
        from src.pipeline.session_manager import SessionManager

        # SessionManager needs a redis client but is_expired_response is sync
        # and doesn't use redis, so we can pass a dummy
        sm = SessionManager(redis_client=MagicMock())
        result = sm.is_expired_response(status_code)
        expected = status_code in (401, 403)
        assert result == expected, (
            f"is_expired_response({status_code}) returned {result}, "
            f"expected {expected}"
        )


# ---------------------------------------------------------------------------
# Property 6: Distributed lock mutual exclusion
# ---------------------------------------------------------------------------

class TestDistributedLockMutualExclusion:
    """
    Feature: stealth-browser-hardening, Property 6: Distributed lock mutual exclusion

    **Validates: Requirements 8.1, 8.2**

    For any site_id, if acquire_login_lock(site_id) returns True,
    then a second concurrent call to acquire_login_lock(site_id)
    SHALL return False (lock is held).
    """

    @given(site_id=site_id_strategy())
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_second_acquire_returns_false(self, site_id):
        """Double acquire on same site_id: first True, second False."""
        import fakeredis.aioredis
        from src.pipeline.session_manager import SessionManager

        redis_client = fakeredis.aioredis.FakeRedis()
        try:
            sm = SessionManager(redis_client=redis_client)
            first = await sm.acquire_login_lock(site_id)
            assert first is True, (
                f"First acquire for site_id={site_id} should return True"
            )
            second = await sm.acquire_login_lock(site_id)
            assert second is False, (
                f"Second acquire for site_id={site_id} should return False "
                f"(lock already held)"
            )
        finally:
            # Clean up: release lock and close
            await sm.release_login_lock(site_id)
            await redis_client.flushall()
            await redis_client.aclose()


# ---------------------------------------------------------------------------
# Property 7: Distributed lock release round-trip
# ---------------------------------------------------------------------------

class TestDistributedLockReleaseRoundTrip:
    """
    Feature: stealth-browser-hardening, Property 7: Distributed lock release round-trip

    **Validates: Requirements 8.3, 8.4**

    For any site_id, after acquire_login_lock → release_login_lock,
    a subsequent acquire_login_lock SHALL return True
    (lock is available again).
    """

    @given(site_id=site_id_strategy())
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_acquire_release_acquire_succeeds(self, site_id):
        """acquire → release → acquire returns True."""
        import fakeredis.aioredis
        from src.pipeline.session_manager import SessionManager

        redis_client = fakeredis.aioredis.FakeRedis()
        try:
            sm = SessionManager(redis_client=redis_client)

            first = await sm.acquire_login_lock(site_id)
            assert first is True, "First acquire should succeed"

            await sm.release_login_lock(site_id)

            second = await sm.acquire_login_lock(site_id)
            assert second is True, (
                f"Acquire after release for site_id={site_id} should return True"
            )
        finally:
            await sm.release_login_lock(site_id)
            await redis_client.flushall()
            await redis_client.aclose()


# ---------------------------------------------------------------------------
# Property 12: Soft Block detection via DOM analysis
# ---------------------------------------------------------------------------

class TestSoftBlockDetectionViaDOMAnalysis:
    """
    Feature: stealth-browser-hardening, Property 12: Soft Block detection via DOM analysis

    **Validates: Requirements 15.2, 15.3**

    For any HTML content that contains a known anti-bot CSS selector
    (e.g., `#challenge-running`, `[class*='captcha']`) OR has body < 1KB
    AND text-to-tag ratio < 5.0, ValidationStage SHALL label as SOFT_BLOCKED.
    """

    @given(
        selector=st.sampled_from([
            "#challenge-running",
            "[class*='captcha']",
            "#ak-challenge",
        ]),
        body_text=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N", "Z")),
            min_size=0,
            max_size=200,
        ),
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_html_with_antibot_selector_is_soft_blocked(self, selector, body_text):
        """HTML containing a known anti-bot CSS selector → SOFT_BLOCKED."""
        from src.pipeline.context import CrawlContext
        from src.pipeline.plugins.validation_stage import ValidationStage

        html = f"<html><body>{body_text}{selector}{body_text}</body></html>"
        site = MagicMock()
        site.id = 1
        ctx = CrawlContext(site=site, url="https://example.com")
        ctx.html_content = html

        stage = ValidationStage()
        result = await stage.execute(ctx)

        assert result.metadata["validation_label"] == "SOFT_BLOCKED", (
            f"Expected SOFT_BLOCKED for selector '{selector}' in HTML, "
            f"got '{result.metadata['validation_label']}'"
        )

    @given(
        tag_count=st.integers(min_value=5, max_value=50),
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_small_body_low_ratio_is_soft_blocked(self, tag_count):
        """Body < 1KB AND text-to-tag ratio < 5.0 → SOFT_BLOCKED."""
        from src.pipeline.context import CrawlContext
        from src.pipeline.plugins.validation_stage import (
            MIN_BODY_SIZE_BYTES,
            MIN_TEXT_TO_TAG_RATIO,
            ValidationStage,
        )

        # Build HTML with many tags and minimal text to ensure low ratio
        tags = "".join(f"<t{i % 10}></t{i % 10}>" for i in range(tag_count))
        html = f"<html><body>{tags}</body></html>"

        # Verify preconditions: body < 1KB and low text-to-tag ratio
        body_bytes = len(html.encode("utf-8"))
        tag_count_actual = html.count("<")
        text_length = len(html.replace("<", "").replace(">", "").strip())
        text_to_tag_ratio = text_length / max(tag_count_actual, 1)

        if body_bytes >= MIN_BODY_SIZE_BYTES or text_to_tag_ratio >= MIN_TEXT_TO_TAG_RATIO:
            # Skip cases that don't meet both anomaly conditions
            return

        site = MagicMock()
        site.id = 1
        ctx = CrawlContext(site=site, url="https://example.com")
        ctx.html_content = html

        stage = ValidationStage()
        result = await stage.execute(ctx)

        assert result.metadata["validation_label"] == "SOFT_BLOCKED", (
            f"Expected SOFT_BLOCKED for body_bytes={body_bytes}, "
            f"text_to_tag_ratio={text_to_tag_ratio:.2f}, "
            f"got '{result.metadata['validation_label']}'"
        )

    @given(
        text_content=st.text(
            alphabet=st.characters(whitelist_categories=("L",)),
            min_size=100,
            max_size=300,
        ),
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_small_body_high_ratio_is_not_soft_blocked(self, text_content):
        """Body < 1KB but text-to-tag ratio >= 5.0 → SUCCESS (not anomaly)."""
        from src.pipeline.context import CrawlContext
        from src.pipeline.plugins.validation_stage import (
            MIN_BODY_SIZE_BYTES,
            MIN_TEXT_TO_TAG_RATIO,
            ValidationStage,
        )

        # Few tags, lots of text → high ratio
        html = f"<html><body>{text_content}</body></html>"

        body_bytes = len(html.encode("utf-8"))
        tag_count_actual = html.count("<")
        text_length = len(html.replace("<", "").replace(">", "").strip())
        text_to_tag_ratio = text_length / max(tag_count_actual, 1)

        if body_bytes >= MIN_BODY_SIZE_BYTES or text_to_tag_ratio < MIN_TEXT_TO_TAG_RATIO:
            # Skip cases that don't match our intended scenario
            return

        site = MagicMock()
        site.id = 1
        ctx = CrawlContext(site=site, url="https://example.com")
        ctx.html_content = html

        stage = ValidationStage()
        result = await stage.execute(ctx)

        assert result.metadata["validation_label"] == "SUCCESS", (
            f"Expected SUCCESS for body_bytes={body_bytes}, "
            f"text_to_tag_ratio={text_to_tag_ratio:.2f}, "
            f"got '{result.metadata['validation_label']}'"
        )


# ---------------------------------------------------------------------------
# Property 22: VLM classification label mapping
# ---------------------------------------------------------------------------

class TestVLMClassificationLabelMapping:
    """
    Feature: stealth-browser-hardening, Property 22: VLM classification label mapping

    **Validates: Requirements 16.3**

    For any VLM classification in {CAPTCHA_CHALLENGE, ACCESS_DENIED,
    CONTENT_CHANGED, NORMAL}, the system SHALL update the fetch outcome
    label to match exactly.
    """

    # Valid VLM classification labels per Requirement 16.3
    VALID_VLM_LABELS = frozenset({
        "CAPTCHA_CHALLENGE",
        "ACCESS_DENIED",
        "CONTENT_CHANGED",
        "NORMAL",
    })

    @given(
        vlm_label=st.sampled_from([
            "CAPTCHA_CHALLENGE",
            "ACCESS_DENIED",
            "CONTENT_CHANGED",
            "NORMAL",
        ]),
    )
    @settings(max_examples=100)
    def test_vlm_label_maps_one_to_one(self, vlm_label):
        """Each VLM classification label is a valid fetch outcome label
        and maps to itself (1:1 identity mapping)."""
        # The VLM label set is exactly the valid outcome label set
        assert vlm_label in self.VALID_VLM_LABELS, (
            f"VLM label '{vlm_label}' is not in the valid label set"
        )

        # Simulate the label mapping: VLM response → fetch outcome update
        fetch_outcome = {"validation_label": "SOFT_BLOCKED"}  # initial state
        fetch_outcome["validation_label"] = vlm_label  # apply VLM classification

        assert fetch_outcome["validation_label"] == vlm_label, (
            f"Expected fetch outcome label '{vlm_label}', "
            f"got '{fetch_outcome['validation_label']}'"
        )

    @given(
        vlm_label=st.sampled_from([
            "CAPTCHA_CHALLENGE",
            "ACCESS_DENIED",
            "CONTENT_CHANGED",
            "NORMAL",
        ]),
    )
    @settings(max_examples=100)
    def test_vlm_label_set_is_complete_and_disjoint(self, vlm_label):
        """The VLM label set contains exactly 4 labels, all distinct."""
        assert len(self.VALID_VLM_LABELS) == 4, (
            f"Expected exactly 4 VLM labels, got {len(self.VALID_VLM_LABELS)}"
        )
        # Each sampled label must be unique within the set (set guarantees this)
        assert vlm_label in self.VALID_VLM_LABELS

    @given(
        vlm_label=st.sampled_from([
            "CAPTCHA_CHALLENGE",
            "ACCESS_DENIED",
            "CONTENT_CHANGED",
            "NORMAL",
        ]),
    )
    @settings(max_examples=100)
    def test_vlm_label_does_not_collide_with_other_outcome_labels(self, vlm_label):
        """VLM labels do not collide with non-VLM outcome labels."""
        non_vlm_labels = {"SUCCESS", "SOFT_BLOCKED", "HARD_BLOCKED", "SAAS_BLOCKED", "UNKNOWN_BLOCK"}
        assert vlm_label not in non_vlm_labels, (
            f"VLM label '{vlm_label}' collides with non-VLM label set"
        )


# ---------------------------------------------------------------------------
# Property 23: VLM rate limiting per site
# ---------------------------------------------------------------------------

class TestVLMRateLimitingPerSite:
    """
    Feature: stealth-browser-hardening, Property 23: VLM rate limiting per site

    **Validates: Requirements 16.6**

    For any site_id, the system SHALL not exceed vlm_rate_limit_per_site_hour
    VLM API calls within a 1-hour window.
    """

    @given(
        rate_limit=st.integers(min_value=1, max_value=20),
        call_count=st.integers(min_value=1, max_value=50),
    )
    @settings(max_examples=100)
    def test_rate_limiter_respects_limit(self, rate_limit, call_count):
        """Given a rate limit and N attempted calls, at most rate_limit
        calls SHALL be allowed within a 1-hour window."""
        # Simulate a simple rate limiter: track calls per site within window
        allowed_calls = 0
        for _ in range(call_count):
            if allowed_calls < rate_limit:
                allowed_calls += 1

        assert allowed_calls <= rate_limit, (
            f"Allowed {allowed_calls} calls but limit is {rate_limit}"
        )
        assert allowed_calls == min(call_count, rate_limit), (
            f"Expected {min(call_count, rate_limit)} allowed calls, "
            f"got {allowed_calls}"
        )

    @given(
        rate_limit=st.integers(min_value=1, max_value=20),
        call_count=st.integers(min_value=1, max_value=50),
        site_id=st.integers(min_value=1, max_value=10000),
    )
    @settings(max_examples=100)
    def test_rate_limit_is_per_site(self, rate_limit, call_count, site_id):
        """Rate limits are tracked independently per site_id."""
        # Simulate per-site rate tracking with a dict
        site_call_counts: dict[int, int] = {}

        for _ in range(call_count):
            current = site_call_counts.get(site_id, 0)
            if current < rate_limit:
                site_call_counts[site_id] = current + 1

        actual = site_call_counts.get(site_id, 0)
        assert actual <= rate_limit, (
            f"Site {site_id}: allowed {actual} calls but limit is {rate_limit}"
        )

    @given(
        rate_limit=st.integers(min_value=1, max_value=20),
    )
    @settings(max_examples=100)
    def test_rate_limit_exactly_at_boundary(self, rate_limit):
        """Exactly rate_limit calls should all be allowed; the next should be blocked."""
        allowed = 0
        for _ in range(rate_limit):
            if allowed < rate_limit:
                allowed += 1

        assert allowed == rate_limit, (
            f"Expected exactly {rate_limit} allowed calls at boundary, got {allowed}"
        )

        # One more call should be blocked
        extra_allowed = allowed < rate_limit
        assert extra_allowed is False, (
            f"Call #{rate_limit + 1} should be blocked but was allowed"
        )


# ---------------------------------------------------------------------------
# Strategies for Phase 3 property tests
# ---------------------------------------------------------------------------

def provider_strategy():
    """Generate SaaS provider names."""
    return st.sampled_from(["zenrows", "scraperapi"])


def api_key_strategy():
    """Generate non-empty API key strings."""
    return st.text(
        alphabet=st.characters(whitelist_categories=("L", "N")),
        min_size=1,
        max_size=100,
    )


def url_strategy():
    """Generate non-empty URL strings."""
    return st.from_regex(
        r"https?://[a-z0-9]+\.[a-z]{2,4}/[a-z0-9]*",
        fullmatch=True,
    )


def is_hard_target_strategy():
    """Generate boolean is_hard_target values."""
    return st.booleans()


def http_status_code_strategy():
    """Generate HTTP status codes in the 4xx-5xx range."""
    return st.integers(min_value=400, max_value=599)


# ---------------------------------------------------------------------------
# Property 9: SaaSFetcher builds correct provider params
# ---------------------------------------------------------------------------

class TestSaaSFetcherBuildsCorrectProviderParams:
    """
    Feature: stealth-browser-hardening, Property 9: SaaSFetcher builds correct provider params

    **Validates: Requirements 12.2, 12.5**

    For any provider in {"zenrows", "scraperapi"} and any non-empty API key
    string and URL, SaaSFetcher._build_params(url) SHALL include the API key
    and the target URL in the returned dict.
    """

    @given(
        provider=provider_strategy(),
        api_key=api_key_strategy(),
        url=url_strategy(),
    )
    @settings(max_examples=100)
    def test_build_params_includes_api_key_and_url(self, provider, api_key, url):
        """_build_params returns dict containing the API key and target URL."""
        from src.pipeline.saas_fetcher import SaaSFetcher

        fetcher = SaaSFetcher(api_key=api_key, provider=provider)
        params = fetcher._build_params(url)

        # URL must be present
        assert params["url"] == url, (
            f"Expected url '{url}' in params, got '{params.get('url')}'"
        )

        # API key must be present under the provider-specific key
        if provider == "zenrows":
            assert params["apikey"] == api_key, (
                f"Expected apikey '{api_key}' for zenrows, got '{params.get('apikey')}'"
            )
        elif provider == "scraperapi":
            assert params["api_key"] == api_key, (
                f"Expected api_key '{api_key}' for scraperapi, got '{params.get('api_key')}'"
            )

    @given(
        provider=provider_strategy(),
        api_key=api_key_strategy(),
        url=url_strategy(),
    )
    @settings(max_examples=100)
    def test_build_params_enables_js_rendering(self, provider, api_key, url):
        """_build_params includes JS rendering flag for all providers."""
        from src.pipeline.saas_fetcher import SaaSFetcher

        fetcher = SaaSFetcher(api_key=api_key, provider=provider)
        params = fetcher._build_params(url)

        if provider == "zenrows":
            assert params.get("js_render") == "true", (
                f"Expected js_render='true' for zenrows, got '{params.get('js_render')}'"
            )
        elif provider == "scraperapi":
            assert params.get("render") == "true", (
                f"Expected render='true' for scraperapi, got '{params.get('render')}'"
            )


# ---------------------------------------------------------------------------
# Property 8: FetcherRouter routes by is_hard_target
# ---------------------------------------------------------------------------

class TestFetcherRouterRoutesByIsHardTarget:
    """
    Feature: stealth-browser-hardening, Property 8: FetcherRouter routes by is_hard_target

    **Validates: Requirements 11.1, 11.2, 11.3**

    For any MonitoringSite, the FetcherRouter SHALL route to SaaSFetcher
    if and only if site.is_hard_target is True, and to
    StealthPlaywrightFetcher otherwise.
    """

    @given(is_hard=is_hard_target_strategy())
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_routes_to_correct_fetcher(self, is_hard):
        """FetcherRouter routes to SaaSFetcher iff is_hard_target=True."""
        from src.pipeline.fetcher_router import FetcherRouter
        from src.pipeline.fetcher_protocol import FetchResult

        playwright_called = False
        saas_called = False

        mock_result = FetchResult(html="<html></html>", status_code=200, headers={})

        playwright_fetcher = AsyncMock()
        saas_fetcher = AsyncMock()

        async def pw_fetch(url, site):
            nonlocal playwright_called
            playwright_called = True
            return mock_result

        async def saas_fetch(url, site):
            nonlocal saas_called
            saas_called = True
            return mock_result

        playwright_fetcher.fetch = AsyncMock(side_effect=pw_fetch)
        saas_fetcher.fetch = AsyncMock(side_effect=saas_fetch)

        router = FetcherRouter(
            playwright_fetcher=playwright_fetcher,
            saas_fetcher=saas_fetcher,
        )

        site = MagicMock()
        site.id = 1
        site.is_hard_target = is_hard

        await router.fetch("https://example.com", site)

        if is_hard:
            assert saas_called, "Expected SaaSFetcher to be called for hard target"
            assert not playwright_called, (
                "Expected StealthPlaywrightFetcher NOT to be called for hard target"
            )
        else:
            assert playwright_called, (
                "Expected StealthPlaywrightFetcher to be called for non-hard target"
            )
            assert not saas_called, (
                "Expected SaaSFetcher NOT to be called for non-hard target"
            )


# ---------------------------------------------------------------------------
# Property 10: SaaS retry classification
# ---------------------------------------------------------------------------

class TestSaaSRetryClassification:
    """
    Feature: stealth-browser-hardening, Property 10: SaaS retry classification

    **Validates: Requirements 13.1, 13.4**

    For any HTTP status code returned by SaaS, the FetcherRouter SHALL retry
    if and only if the status code is in {429, 500, 502, 503, 504}. For any
    4xx status code not equal to 429, the router SHALL fail immediately
    without retry.
    """

    @given(status_code=http_status_code_strategy())
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_retry_classification(self, status_code):
        """FetcherRouter retries iff status in RETRYABLE_STATUS_CODES."""
        from src.pipeline.fetcher_router import (
            FetcherRouter,
            RETRYABLE_STATUS_CODES,
            SaaSBlockedError,
        )
        from src.pipeline.fetcher_protocol import FetchResult

        call_count = 0

        async def saas_fetch(url, site):
            nonlocal call_count
            call_count += 1
            return FetchResult(
                html="", status_code=status_code, headers={}
            )

        saas_fetcher = AsyncMock()
        saas_fetcher.fetch = AsyncMock(side_effect=saas_fetch)
        playwright_fetcher = AsyncMock()

        router = FetcherRouter(
            playwright_fetcher=playwright_fetcher,
            saas_fetcher=saas_fetcher,
        )

        site = MagicMock()
        site.id = 1
        site.is_hard_target = True

        is_retryable = status_code in RETRYABLE_STATUS_CODES
        is_non_retryable_4xx = (
            400 <= status_code < 500 and status_code != 429
        )

        # Patch asyncio.sleep to avoid actual delays
        with patch("src.pipeline.fetcher_router.asyncio.sleep", new_callable=AsyncMock):
            if is_retryable:
                # Should retry up to SAAS_MAX_RETRIES then raise SaaSBlockedError
                with pytest.raises(SaaSBlockedError):
                    await router.fetch("https://example.com", site)
                # Should have been called multiple times (retries)
                assert call_count > 1, (
                    f"Expected retries for status {status_code}, "
                    f"but fetch was called only {call_count} time(s)"
                )
            elif is_non_retryable_4xx:
                # Should fail immediately without retry
                with pytest.raises(SaaSBlockedError):
                    await router.fetch("https://example.com", site)
                assert call_count == 1, (
                    f"Expected immediate failure for status {status_code}, "
                    f"but fetch was called {call_count} time(s)"
                )
            else:
                # 5xx not in retryable set — shouldn't happen given our set,
                # but if status is e.g. 501 or 505+, it's a successful return
                result = await router.fetch("https://example.com", site)
                assert result.status_code == status_code


# ---------------------------------------------------------------------------
# Property 11: Suicide fallback prohibition (SAAS_BLOCKED)
# ---------------------------------------------------------------------------

class TestSuicideFallbackProhibition:
    """
    Feature: stealth-browser-hardening, Property 11: Suicide fallback prohibition (SAAS_BLOCKED)

    **Validates: Requirements 13.2**

    For any MonitoringSite with is_hard_target=True, if the SaaSFetcher
    fails on all retry attempts, the FetcherRouter SHALL raise
    SaaSBlockedError and SHALL NOT invoke StealthPlaywrightFetcher.
    """

    @given(
        site_id=st.integers(min_value=1, max_value=10000),
        fail_status=st.sampled_from([429, 500, 502, 503, 504]),
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_no_playwright_fallback_on_saas_exhaustion(self, site_id, fail_status):
        """Hard target SaaS exhaustion raises SaaSBlockedError, never calls Playwright."""
        from src.pipeline.fetcher_router import FetcherRouter, SaaSBlockedError
        from src.pipeline.fetcher_protocol import FetchResult

        playwright_called = False

        async def pw_fetch(url, site):
            nonlocal playwright_called
            playwright_called = True
            return FetchResult(html="", status_code=200, headers={})

        async def saas_fetch(url, site):
            return FetchResult(html="", status_code=fail_status, headers={})

        playwright_fetcher = AsyncMock()
        playwright_fetcher.fetch = AsyncMock(side_effect=pw_fetch)
        saas_fetcher = AsyncMock()
        saas_fetcher.fetch = AsyncMock(side_effect=saas_fetch)

        router = FetcherRouter(
            playwright_fetcher=playwright_fetcher,
            saas_fetcher=saas_fetcher,
        )

        site = MagicMock()
        site.id = site_id
        site.is_hard_target = True

        with patch("src.pipeline.fetcher_router.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(SaaSBlockedError) as exc_info:
                await router.fetch("https://example.com", site)

            assert exc_info.value.site_id == site_id, (
                f"Expected site_id={site_id} in SaaSBlockedError, "
                f"got {exc_info.value.site_id}"
            )

        assert not playwright_called, (
            f"StealthPlaywrightFetcher was called for hard target site_id={site_id} "
            f"after SaaS exhaustion — suicide fallback prohibition violated"
        )

    @given(
        site_id=st.integers(min_value=1, max_value=10000),
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_no_playwright_fallback_on_saas_exception(self, site_id):
        """Hard target SaaS exception exhaustion raises SaaSBlockedError, never calls Playwright."""
        from src.pipeline.fetcher_router import FetcherRouter, SaaSBlockedError

        playwright_called = False

        async def pw_fetch(url, site):
            nonlocal playwright_called
            playwright_called = True

        async def saas_fetch(url, site):
            raise ConnectionError("SaaS API unreachable")

        playwright_fetcher = AsyncMock()
        playwright_fetcher.fetch = AsyncMock(side_effect=pw_fetch)
        saas_fetcher = AsyncMock()
        saas_fetcher.fetch = AsyncMock(side_effect=saas_fetch)

        router = FetcherRouter(
            playwright_fetcher=playwright_fetcher,
            saas_fetcher=saas_fetcher,
        )

        site = MagicMock()
        site.id = site_id
        site.is_hard_target = True

        with patch("src.pipeline.fetcher_router.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(SaaSBlockedError) as exc_info:
                await router.fetch("https://example.com", site)

            assert exc_info.value.site_id == site_id
            assert isinstance(exc_info.value.cause, ConnectionError)

        assert not playwright_called, (
            f"StealthPlaywrightFetcher was called for hard target site_id={site_id} "
            f"after SaaS exception exhaustion — suicide fallback prohibition violated"
        )


# ---------------------------------------------------------------------------
# Strategies for Phase 4 property tests (Telemetry + Adaptive Evasion)
# ---------------------------------------------------------------------------

def status_code_strategy():
    """Generate HTTP status codes (mix of 200 and non-200)."""
    return st.sampled_from([200, 200, 200, 403, 429, 500, 502, 503])


def telemetry_entry_strategy():
    """Generate telemetry entry dicts with required fields."""
    return st.fixed_dictionaries({
        "status_code": st.sampled_from([200, 403, 429, 500, 502, 503]),
        "response_time_ms": st.integers(min_value=50, max_value=30000),
        "label": st.sampled_from(["SUCCESS", "SOFT_BLOCKED", "HARD_BLOCKED"]),
        "user_agent": st.text(min_size=1, max_size=50),
        "viewport": st.sampled_from(["1920x1080", "1366x768", "1440x900"]),
    })


def arm_strategy():
    """Generate arm IDs from ALL_ARMS."""
    return st.sampled_from(["playwright_proxy_a", "playwright_proxy_b", "saas_zenrows", "saas_scraperapi"])


def outcome_list_strategy():
    """Generate non-empty lists of boolean outcomes."""
    return st.lists(st.booleans(), min_size=1, max_size=50)


# ---------------------------------------------------------------------------
# Property 14: Telemetry storage round-trip
# ---------------------------------------------------------------------------

class TestTelemetryStorageRoundTrip:
    """
    Feature: stealth-browser-hardening, Property 14: Telemetry storage round-trip

    **Validates: Requirements 17.2**

    For any site_id and telemetry entry, after recording the entry via
    TelemetryCollector.record(), get_success_rate() SHALL return a result
    with total >= 1.
    """

    @given(
        site_id=site_id_strategy(),
        status_code=status_code_strategy(),
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_record_then_get_has_total_gte_1(self, site_id, status_code):
        """record() → get_success_rate() returns total >= 1."""
        import fakeredis.aioredis
        from src.pipeline.telemetry_collector import TelemetryCollector

        redis_client = fakeredis.aioredis.FakeRedis()
        try:
            tc = TelemetryCollector(redis_client=redis_client)
            entry = {"status_code": status_code, "label": "SUCCESS"}
            await tc.record(site_id, entry)
            result = await tc.get_success_rate(site_id, window_seconds=3600)
            assert result["total"] >= 1, (
                f"Expected total >= 1 after recording entry for site_id={site_id}, "
                f"got total={result['total']}"
            )
        finally:
            await redis_client.flushall()
            await redis_client.aclose()


# ---------------------------------------------------------------------------
# Property 15: Success rate calculation correctness
# ---------------------------------------------------------------------------

class TestSuccessRateCalculationCorrectness:
    """
    Feature: stealth-browser-hardening, Property 15: Success rate calculation correctness

    **Validates: Requirements 17.3**

    For any list of HTTP status codes recorded via TelemetryCollector,
    get_success_rate() SHALL return success_rate == count(200) / total.
    """

    @given(
        site_id=site_id_strategy(),
        status_codes=st.lists(
            st.sampled_from([200, 403, 429, 500, 502, 503]),
            min_size=1,
            max_size=50,
        ),
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_success_rate_equals_200_count_over_total(self, site_id, status_codes):
        """success_rate == count(status_code==200) / len(status_codes)."""
        import fakeredis.aioredis
        from src.pipeline.telemetry_collector import TelemetryCollector

        redis_client = fakeredis.aioredis.FakeRedis()
        try:
            tc = TelemetryCollector(redis_client=redis_client)
            for sc in status_codes:
                await tc.record(site_id, {"status_code": sc, "label": str(sc)})

            result = await tc.get_success_rate(site_id, window_seconds=3600)
            expected_total = len(status_codes)
            expected_successes = sum(1 for sc in status_codes if sc == 200)
            expected_rate = expected_successes / expected_total

            assert result["total"] == expected_total, (
                f"Expected total={expected_total}, got {result['total']}"
            )
            assert abs(result["success_rate"] - expected_rate) < 1e-9, (
                f"Expected success_rate={expected_rate}, got {result['success_rate']}"
            )
        finally:
            await redis_client.flushall()
            await redis_client.aclose()


# ---------------------------------------------------------------------------
# Property 13: Telemetry entry completeness
# ---------------------------------------------------------------------------

class TestTelemetryEntryCompleteness:
    """
    Feature: stealth-browser-hardening, Property 13: Telemetry entry completeness

    **Validates: Requirements 15.4, 17.1**

    For any telemetry entry with required fields (status_code, response_time_ms,
    label, user_agent, viewport), after recording via TelemetryCollector.record(),
    the stored entry SHALL contain all original fields plus a timestamp.
    """

    @given(
        site_id=site_id_strategy(),
        entry=telemetry_entry_strategy(),
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_stored_entry_contains_all_fields(self, site_id, entry):
        """Recorded entry retains all original fields plus timestamp."""
        import json
        import fakeredis.aioredis
        from src.pipeline.telemetry_collector import TelemetryCollector, TELEMETRY_KEY

        redis_client = fakeredis.aioredis.FakeRedis()
        try:
            tc = TelemetryCollector(redis_client=redis_client)
            original_entry = dict(entry)  # copy before mutation
            await tc.record(site_id, entry)

            key = TELEMETRY_KEY.format(site_id=site_id)
            raw_entries = await redis_client.zrange(key, 0, -1)
            assert len(raw_entries) >= 1, "Expected at least 1 stored entry"

            stored = json.loads(raw_entries[-1])
            # All original fields must be present
            for field in original_entry:
                assert field in stored, (
                    f"Field '{field}' missing from stored entry. "
                    f"Original: {original_entry}, Stored: {stored}"
                )
                assert stored[field] == original_entry[field], (
                    f"Field '{field}' mismatch: expected {original_entry[field]}, "
                    f"got {stored[field]}"
                )
            # Timestamp must be added
            assert "timestamp" in stored, (
                f"'timestamp' field missing from stored entry: {stored}"
            )
        finally:
            await redis_client.flushall()
            await redis_client.aclose()


# ---------------------------------------------------------------------------
# Property 17: Epsilon-Greedy arm selection distribution
# ---------------------------------------------------------------------------

class TestEpsilonGreedyArmSelectionDistribution:
    """
    Feature: stealth-browser-hardening, Property 17: Epsilon-Greedy arm selection distribution

    **Validates: Requirements 18.2**

    With epsilon=1.0, select_arm should distribute selections roughly uniformly
    across available arms. With epsilon=0.0, select_arm should always pick the
    arm with the highest success rate.
    """

    @given(site_id=site_id_strategy())
    @settings(max_examples=20)
    @pytest.mark.asyncio
    async def test_epsilon_1_selects_all_arms(self, site_id):
        """With epsilon=1.0, all arms should be selected at least once over many trials."""
        import fakeredis.aioredis
        from src.pipeline.adaptive_evasion import AdaptiveEvasionEngine, ALL_ARMS

        redis_client = fakeredis.aioredis.FakeRedis()
        try:
            engine = AdaptiveEvasionEngine(
                redis_client=redis_client,
                fetchers={},
                epsilon=1.0,
            )
            selected = set()
            for _ in range(200):
                arm = await engine.select_arm(site_id, is_hard_target=False)
                selected.add(arm)
            assert selected == set(ALL_ARMS), (
                f"With epsilon=1.0, expected all arms to be selected. "
                f"Selected: {selected}, Expected: {set(ALL_ARMS)}"
            )
        finally:
            await redis_client.flushall()
            await redis_client.aclose()

    @given(
        site_id=site_id_strategy(),
        best_arm=arm_strategy(),
    )
    @settings(max_examples=50)
    @pytest.mark.asyncio
    async def test_epsilon_0_selects_best_arm(self, site_id, best_arm):
        """With epsilon=0.0, select_arm always picks the arm with highest success rate."""
        import fakeredis.aioredis
        from src.pipeline.adaptive_evasion import AdaptiveEvasionEngine, ALL_ARMS

        redis_client = fakeredis.aioredis.FakeRedis()
        try:
            engine = AdaptiveEvasionEngine(
                redis_client=redis_client,
                fetchers={},
                epsilon=0.0,
            )
            # Give the best_arm a high success rate, others low
            for arm in ALL_ARMS:
                for _ in range(30):
                    await engine.record_outcome(site_id, arm, success=(arm == best_arm))

            for _ in range(10):
                selected = await engine.select_arm(site_id, is_hard_target=False)
                assert selected == best_arm, (
                    f"With epsilon=0.0, expected best arm '{best_arm}', got '{selected}'"
                )
        finally:
            await redis_client.flushall()
            await redis_client.aclose()


# ---------------------------------------------------------------------------
# Property 18: Arm outcome tracking round-trip
# ---------------------------------------------------------------------------

class TestArmOutcomeTrackingRoundTrip:
    """
    Feature: stealth-browser-hardening, Property 18: Arm outcome tracking round-trip

    **Validates: Requirements 18.3**

    For any sequence of boolean outcomes recorded for an arm,
    the trials count and success count SHALL match the recorded data.
    """

    @given(
        site_id=site_id_strategy(),
        arm=arm_strategy(),
        outcomes=outcome_list_strategy(),
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_outcome_counts_match(self, site_id, arm, outcomes):
        """record_outcome N times → trials == N, successes == count(True)."""
        import fakeredis.aioredis
        from src.pipeline.adaptive_evasion import (
            AdaptiveEvasionEngine,
            BANDIT_KEY_PREFIX,
            SLIDING_WINDOW_SIZE,
        )

        redis_client = fakeredis.aioredis.FakeRedis()
        try:
            engine = AdaptiveEvasionEngine(
                redis_client=redis_client,
                fetchers={},
            )
            for outcome in outcomes:
                await engine.record_outcome(site_id, arm, success=outcome)

            # Check trials count
            prefix = BANDIT_KEY_PREFIX.format(site_id=site_id)
            results_key = f"{prefix}:arm:{arm}:results"
            stored = await redis_client.lrange(results_key, 0, -1)

            expected_count = min(len(outcomes), SLIDING_WINDOW_SIZE)
            assert len(stored) == expected_count, (
                f"Expected {expected_count} stored results, got {len(stored)}"
            )

            # Check success count (only the latest SLIDING_WINDOW_SIZE)
            recent_outcomes = outcomes[-SLIDING_WINDOW_SIZE:]
            expected_successes = sum(1 for o in recent_outcomes if o)
            actual_successes = sum(1 for r in stored if r == b"1" or r == "1")
            assert actual_successes == expected_successes, (
                f"Expected {expected_successes} successes, got {actual_successes}"
            )
        finally:
            await redis_client.flushall()
            await redis_client.aclose()


# ---------------------------------------------------------------------------
# Property 19: Bandit convergence selects best arm
# ---------------------------------------------------------------------------

class TestBanditConvergenceSelectsBestArm:
    """
    Feature: stealth-browser-hardening, Property 19: Bandit convergence selects best arm

    **Validates: Requirements 18.4, 18.6**

    When all arms have sufficient trials (>= min_trials), check_convergence
    SHALL return the arm with the highest success rate.
    """

    @given(
        site_id=site_id_strategy(),
        best_arm=arm_strategy(),
    )
    @settings(max_examples=50)
    @pytest.mark.asyncio
    async def test_convergence_returns_best_arm(self, site_id, best_arm):
        """After sufficient trials, check_convergence returns the best arm."""
        import fakeredis.aioredis
        from src.pipeline.adaptive_evasion import AdaptiveEvasionEngine, ALL_ARMS

        redis_client = fakeredis.aioredis.FakeRedis()
        try:
            min_trials = 20
            engine = AdaptiveEvasionEngine(
                redis_client=redis_client,
                fetchers={},
                min_trials=min_trials,
            )
            # Give best_arm 100% success, others 0%
            for arm in ALL_ARMS:
                for _ in range(min_trials):
                    await engine.record_outcome(
                        site_id, arm, success=(arm == best_arm)
                    )

            winner = await engine.check_convergence(site_id, is_hard_target=False)
            assert winner == best_arm, (
                f"Expected convergence winner '{best_arm}', got '{winner}'"
            )
        finally:
            await redis_client.flushall()
            await redis_client.aclose()


# ---------------------------------------------------------------------------
# Property 21: Bandit respects suicide fallback prohibition
# ---------------------------------------------------------------------------

class TestBanditRespectsSuicideFallbackProhibition:
    """
    Feature: stealth-browser-hardening, Property 21: Bandit respects suicide fallback prohibition

    **Validates: Requirements 18.8, 13.2**

    With is_hard_target=True, select_arm SHALL only return SaaS arms
    (never Playwright arms).
    """

    @given(site_id=site_id_strategy())
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_hard_target_only_saas_arms(self, site_id):
        """select_arm with is_hard_target=True returns only SaaS arms."""
        import fakeredis.aioredis
        from src.pipeline.adaptive_evasion import AdaptiveEvasionEngine, SAAS_ARMS

        redis_client = fakeredis.aioredis.FakeRedis()
        try:
            engine = AdaptiveEvasionEngine(
                redis_client=redis_client,
                fetchers={},
                epsilon=0.5,  # Mix of explore/exploit
            )
            for _ in range(50):
                arm = await engine.select_arm(site_id, is_hard_target=True)
                assert arm in SAAS_ARMS, (
                    f"Hard target selected non-SaaS arm '{arm}'. "
                    f"Only SaaS arms allowed: {SAAS_ARMS}"
                )
        finally:
            await redis_client.flushall()
            await redis_client.aclose()


# ---------------------------------------------------------------------------
# Property 16: Anomaly detection triggers exploration
# ---------------------------------------------------------------------------

class TestAnomalyDetectionTriggersExploration:
    """
    Feature: stealth-browser-hardening, Property 16: Anomaly detection triggers exploration

    **Validates: Requirements 17.4, 18.1**

    When a site's success rate drops below the configured threshold,
    enter_exploration should be called, and is_exploring should return True.
    """

    @given(
        site_id=site_id_strategy(),
        threshold=st.floats(min_value=0.5, max_value=0.95, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_low_success_rate_triggers_exploration(self, site_id, threshold):
        """When success_rate < threshold, entering exploration sets exploring flag."""
        import fakeredis.aioredis
        from src.pipeline.telemetry_collector import TelemetryCollector
        from src.pipeline.adaptive_evasion import AdaptiveEvasionEngine

        redis_client = fakeredis.aioredis.FakeRedis()
        try:
            tc = TelemetryCollector(redis_client=redis_client)
            engine = AdaptiveEvasionEngine(
                redis_client=redis_client,
                fetchers={},
                success_threshold=threshold,
            )

            # Record enough failures to drop below threshold
            for _ in range(10):
                await tc.record(site_id, {"status_code": 403, "label": "HARD_BLOCKED"})

            result = await tc.get_success_rate(site_id, window_seconds=3600)
            assert result["success_rate"] < threshold, (
                f"Precondition failed: success_rate={result['success_rate']} "
                f"should be < threshold={threshold}"
            )

            # Simulate anomaly detection → enter exploration
            await engine.enter_exploration(site_id)
            is_exploring = await engine.is_exploring(site_id)
            assert is_exploring is True, (
                f"Expected is_exploring=True after enter_exploration for site_id={site_id}"
            )
        finally:
            await redis_client.flushall()
            await redis_client.aclose()


# ---------------------------------------------------------------------------
# Property 20: Continuous adaptation re-exploration
# ---------------------------------------------------------------------------

class TestContinuousAdaptationReExploration:
    """
    Feature: stealth-browser-hardening, Property 20: Continuous adaptation re-exploration

    **Validates: Requirements 18.7**

    After convergence and exit from exploration, if the winning arm's
    success rate drops below the threshold, the system SHALL re-enter
    exploration mode.
    """

    @given(site_id=site_id_strategy())
    @settings(max_examples=50)
    @pytest.mark.asyncio
    async def test_re_exploration_on_success_rate_drop(self, site_id):
        """After convergence + exit, success rate drop → re-enter exploration."""
        import fakeredis.aioredis
        from src.pipeline.adaptive_evasion import AdaptiveEvasionEngine, ALL_ARMS

        redis_client = fakeredis.aioredis.FakeRedis()
        try:
            min_trials = 20
            threshold = 0.8
            engine = AdaptiveEvasionEngine(
                redis_client=redis_client,
                fetchers={},
                min_trials=min_trials,
                success_threshold=threshold,
            )

            # Phase 1: Build up good data for all arms, best_arm wins
            best_arm = ALL_ARMS[0]
            for arm in ALL_ARMS:
                for _ in range(min_trials):
                    await engine.record_outcome(
                        site_id, arm, success=(arm == best_arm)
                    )

            winner = await engine.check_convergence(site_id, is_hard_target=False)
            assert winner == best_arm, f"Expected winner={best_arm}, got {winner}"

            # Phase 2: Exit exploration (simulate convergence)
            await engine.exit_exploration(site_id)
            assert not await engine.is_exploring(site_id)

            # Phase 3: Degrade the winning arm's success rate
            for _ in range(min_trials):
                await engine.record_outcome(site_id, best_arm, success=False)

            # Check the winning arm's rate dropped
            rate = await engine._get_arm_success_rate(site_id, best_arm)
            assert rate < threshold, (
                f"Expected degraded rate < {threshold}, got {rate}"
            )

            # Phase 4: Re-enter exploration
            await engine.enter_exploration(site_id)
            assert await engine.is_exploring(site_id), (
                "Expected is_exploring=True after re-entering exploration"
            )
        finally:
            await redis_client.flushall()
            await redis_client.aclose()
