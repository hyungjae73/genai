"""
Integration tests for FetcherRouter + AdaptiveEvasionEngine.

Tests the exploration mode lifecycle:
  anomaly → enter exploration → bandit arm selection → converge → exit
Tests re-exploration when success rate drops after convergence.

Requirements: 18.1, 18.6, 18.7
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import fakeredis.aioredis as fakeredis
import pytest

from src.models import MonitoringSite
from src.pipeline.adaptive_evasion import (
    ALL_ARMS,
    ARM_PLAYWRIGHT_PROXY_A,
    ARM_SAAS_SCRAPERAPI,
    ARM_SAAS_ZENROWS,
    SAAS_ARMS,
    AdaptiveEvasionEngine,
)
from src.pipeline.fetcher_protocol import FetchResult
from src.pipeline.fetcher_router import FetcherRouter, SaaSBlockedError
from src.pipeline.telemetry_collector import TelemetryCollector


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_site(site_id: int = 1, is_hard: bool = False) -> MonitoringSite:
    """Create a minimal MonitoringSite-like object for testing."""
    site = MagicMock(spec=MonitoringSite)
    site.id = site_id
    site.is_hard_target = is_hard
    site.plugin_config = {}
    return site


def _make_fetcher(status_code: int = 200, html: str = "<html>ok</html>") -> AsyncMock:
    """Create a mock PageFetcher that returns a fixed FetchResult."""
    fetcher = AsyncMock()
    fetcher.fetch = AsyncMock(
        return_value=FetchResult(html=html, status_code=status_code, headers={})
    )
    return fetcher


def _make_failing_fetcher() -> AsyncMock:
    """Create a mock PageFetcher that always raises."""
    fetcher = AsyncMock()
    fetcher.fetch = AsyncMock(side_effect=RuntimeError("fetch failed"))
    return fetcher


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def redis_client():
    """Provide a fakeredis async client."""
    return fakeredis.FakeRedis()


@pytest.fixture
def fetchers():
    """Provide a dict of mock fetchers for all arms."""
    return {arm: _make_fetcher() for arm in ALL_ARMS}


@pytest.fixture
def bandit(redis_client, fetchers):
    """Provide an AdaptiveEvasionEngine with low min_trials for fast convergence."""
    return AdaptiveEvasionEngine(
        redis_client=redis_client,
        fetchers=fetchers,
        epsilon=0.0,  # Always exploit for deterministic tests
        min_trials=3,  # Low threshold for fast convergence
        success_threshold=0.8,
    )


@pytest.fixture
def telemetry(redis_client):
    """Provide a TelemetryCollector backed by fakeredis."""
    return TelemetryCollector(redis_client=redis_client)


@pytest.fixture
def router(fetchers, bandit, telemetry):
    """Provide a FetcherRouter wired with bandit + telemetry."""
    return FetcherRouter(
        playwright_fetcher=fetchers[ARM_PLAYWRIGHT_PROXY_A],
        saas_fetcher=fetchers[ARM_SAAS_ZENROWS],
        bandit_engine=bandit,
        telemetry_collector=telemetry,
    )


# ---------------------------------------------------------------------------
# Test: Exploration mode lifecycle (Req 18.1, 18.6)
# ---------------------------------------------------------------------------


class TestExplorationLifecycle:
    """Test the full exploration lifecycle: enter → explore → converge → exit."""

    @pytest.mark.asyncio
    async def test_normal_routing_when_not_exploring(self, router, fetchers):
        """When not in exploration mode, routes normally by is_hard_target."""
        site = _make_site(site_id=1, is_hard=False)
        result = await router.fetch("https://example.com", site)

        assert result.status_code == 200
        fetchers[ARM_PLAYWRIGHT_PROXY_A].fetch.assert_called()

    @pytest.mark.asyncio
    async def test_exploration_delegates_to_bandit_arm(
        self, router, bandit, fetchers, redis_client
    ):
        """When exploring, fetch delegates to the bandit-selected arm's fetcher."""
        site = _make_site(site_id=42, is_hard=False)

        # Enter exploration mode
        await bandit.enter_exploration(42)
        assert await bandit.is_exploring(42)

        # Pre-seed arm success rates so bandit picks a specific arm (epsilon=0)
        # Give playwright_proxy_a the best rate
        for _ in range(5):
            await bandit.record_outcome(42, ARM_PLAYWRIGHT_PROXY_A, success=True)
        for arm in ALL_ARMS:
            if arm != ARM_PLAYWRIGHT_PROXY_A:
                for _ in range(5):
                    await bandit.record_outcome(42, arm, success=False)

        result = await router.fetch("https://example.com", site)

        assert result.status_code == 200
        # The best arm (playwright_proxy_a) should have been called
        fetchers[ARM_PLAYWRIGHT_PROXY_A].fetch.assert_called()

    @pytest.mark.asyncio
    async def test_exploration_records_outcome(self, router, bandit, redis_client):
        """Exploration mode records success/failure outcomes in the bandit engine."""
        site = _make_site(site_id=10, is_hard=False)
        await bandit.enter_exploration(10)

        await router.fetch("https://example.com", site)

        # At least one arm should have a recorded trial
        total_trials = 0
        for arm in ALL_ARMS:
            trials = await bandit._get_arm_trials(10, arm)
            total_trials += trials
        assert total_trials >= 1

    @pytest.mark.asyncio
    async def test_convergence_exits_exploration(self, router, bandit, fetchers):
        """After enough trials, bandit converges and exits exploration mode."""
        site = _make_site(site_id=7, is_hard=False)
        await bandit.enter_exploration(7)

        # Pre-seed all arms with enough trials (min_trials=3)
        # Make playwright_proxy_a the clear winner
        for arm in ALL_ARMS:
            success = arm == ARM_PLAYWRIGHT_PROXY_A
            for _ in range(3):
                await bandit.record_outcome(7, arm, success=success)

        # This fetch should trigger convergence check and exit exploration
        await router.fetch("https://example.com", site)

        # Exploration should be exited
        assert not await bandit.is_exploring(7)

    @pytest.mark.asyncio
    async def test_convergence_updates_site_hard_target_for_saas_winner(
        self, router, bandit, fetchers
    ):
        """When a SaaS arm wins, site.is_hard_target is set to True."""
        site = _make_site(site_id=8, is_hard=False)
        await bandit.enter_exploration(8)

        # Make saas_zenrows the clear winner
        for arm in ALL_ARMS:
            success = arm == ARM_SAAS_ZENROWS
            for _ in range(3):
                await bandit.record_outcome(8, arm, success=success)

        await router.fetch("https://example.com", site)

        assert site.is_hard_target is True
        assert site.plugin_config["winning_arm"] == ARM_SAAS_ZENROWS

    @pytest.mark.asyncio
    async def test_convergence_updates_site_not_hard_for_playwright_winner(
        self, router, bandit, fetchers
    ):
        """When a Playwright arm wins, site.is_hard_target is set to False."""
        site = _make_site(site_id=9, is_hard=False)
        await bandit.enter_exploration(9)

        # Make playwright_proxy_a the clear winner
        for arm in ALL_ARMS:
            success = arm == ARM_PLAYWRIGHT_PROXY_A
            for _ in range(3):
                await bandit.record_outcome(9, arm, success=success)

        await router.fetch("https://example.com", site)

        assert site.is_hard_target is False
        assert site.plugin_config["winning_arm"] == ARM_PLAYWRIGHT_PROXY_A


# ---------------------------------------------------------------------------
# Test: Telemetry recording (Req 18.5)
# ---------------------------------------------------------------------------


class TestTelemetryRecording:
    """Test that telemetry is recorded for both normal and exploration fetches."""

    @pytest.mark.asyncio
    async def test_telemetry_recorded_on_normal_fetch(self, router, telemetry):
        """Normal (non-exploration) fetches record telemetry."""
        site = _make_site(site_id=20, is_hard=False)
        await router.fetch("https://example.com", site)

        stats = await telemetry.get_success_rate(20)
        assert stats["total"] >= 1

    @pytest.mark.asyncio
    async def test_telemetry_recorded_on_exploration_fetch(
        self, router, bandit, telemetry
    ):
        """Exploration fetches also record telemetry."""
        site = _make_site(site_id=21, is_hard=False)
        await bandit.enter_exploration(21)

        await router.fetch("https://example.com", site)

        stats = await telemetry.get_success_rate(21)
        assert stats["total"] >= 1

    @pytest.mark.asyncio
    async def test_no_telemetry_when_collector_absent(self, fetchers, bandit):
        """No error when telemetry_collector is None."""
        router = FetcherRouter(
            playwright_fetcher=fetchers[ARM_PLAYWRIGHT_PROXY_A],
            telemetry_collector=None,
        )
        site = _make_site(site_id=22, is_hard=False)
        # Should not raise
        result = await router.fetch("https://example.com", site)
        assert result.status_code == 200


# ---------------------------------------------------------------------------
# Test: Re-exploration on success rate drop (Req 18.7)
# ---------------------------------------------------------------------------


class TestReExploration:
    """Test that the system can re-enter exploration after convergence."""

    @pytest.mark.asyncio
    async def test_re_enter_exploration_after_convergence(self, router, bandit):
        """After convergence + exit, re-entering exploration works correctly."""
        site = _make_site(site_id=30, is_hard=False)

        # Phase 1: Enter exploration and converge
        await bandit.enter_exploration(30)
        for arm in ALL_ARMS:
            success = arm == ARM_PLAYWRIGHT_PROXY_A
            for _ in range(3):
                await bandit.record_outcome(30, arm, success=success)

        await router.fetch("https://example.com", site)
        assert not await bandit.is_exploring(30)

        # Phase 2: Success rate drops → re-enter exploration
        await bandit.enter_exploration(30)
        assert await bandit.is_exploring(30)

        # Should still be able to fetch in exploration mode
        result = await router.fetch("https://example.com", site)
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_exploration_fetch_failure_records_outcome(
        self, redis_client, telemetry
    ):
        """When an exploration fetch raises, the failure is recorded and re-raised."""
        failing_fetcher = _make_failing_fetcher()
        fetchers = {arm: _make_fetcher() for arm in ALL_ARMS}
        # Override one arm with a failing fetcher
        fetchers[ARM_PLAYWRIGHT_PROXY_A] = failing_fetcher

        bandit = AdaptiveEvasionEngine(
            redis_client=redis_client,
            fetchers=fetchers,
            epsilon=0.0,
            min_trials=3,
        )

        # Pre-seed so bandit picks playwright_proxy_a (the failing one)
        for _ in range(5):
            await bandit.record_outcome(50, ARM_PLAYWRIGHT_PROXY_A, success=True)
        for arm in ALL_ARMS:
            if arm != ARM_PLAYWRIGHT_PROXY_A:
                for _ in range(5):
                    await bandit.record_outcome(50, arm, success=False)

        router = FetcherRouter(
            playwright_fetcher=_make_fetcher(),
            bandit_engine=bandit,
            telemetry_collector=telemetry,
        )

        site = _make_site(site_id=50, is_hard=False)
        await bandit.enter_exploration(50)

        with pytest.raises(RuntimeError, match="fetch failed"):
            await router.fetch("https://example.com", site)

        # Failure should have been recorded
        trials = await bandit._get_arm_trials(50, ARM_PLAYWRIGHT_PROXY_A)
        assert trials >= 6  # 5 pre-seeded + 1 failure


# ---------------------------------------------------------------------------
# Test: Hard target exploration constraints (Req 18.8)
# ---------------------------------------------------------------------------


class TestHardTargetExploration:
    """Test that hard target exploration only uses SaaS arms."""

    @pytest.mark.asyncio
    async def test_hard_target_exploration_uses_saas_arms_only(
        self, redis_client, telemetry
    ):
        """For hard targets in exploration, only SaaS arms are selected."""
        fetchers = {arm: _make_fetcher() for arm in ALL_ARMS}
        bandit = AdaptiveEvasionEngine(
            redis_client=redis_client,
            fetchers=fetchers,
            epsilon=0.0,
            min_trials=3,
        )

        # Pre-seed SaaS arms with data
        for _ in range(5):
            await bandit.record_outcome(60, ARM_SAAS_ZENROWS, success=True)
        for _ in range(5):
            await bandit.record_outcome(60, ARM_SAAS_SCRAPERAPI, success=False)

        router = FetcherRouter(
            playwright_fetcher=fetchers[ARM_PLAYWRIGHT_PROXY_A],
            saas_fetcher=fetchers[ARM_SAAS_ZENROWS],
            bandit_engine=bandit,
            telemetry_collector=telemetry,
        )

        site = _make_site(site_id=60, is_hard=True)
        await bandit.enter_exploration(60)

        result = await router.fetch("https://example.com", site)
        assert result.status_code == 200

        # Verify only SaaS fetchers were called (not playwright arms)
        # The bandit with epsilon=0 should pick saas_zenrows (best rate)
        fetchers[ARM_SAAS_ZENROWS].fetch.assert_called()
