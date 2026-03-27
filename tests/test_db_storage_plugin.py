"""
Unit tests for DBStoragePlugin.

Feature: crawl-pipeline-architecture
Validates: Requirements 12.1-12.5, 20.1-20.5
"""

from unittest.mock import MagicMock, call

import pytest

from src.models import MonitoringSite
from src.pipeline.context import CrawlContext
from src.pipeline.plugins.db_storage_plugin import DBStoragePlugin


def _make_ctx(evidence_count=0, violation_count=0):
    """Helper to build a CrawlContext with evidence records and violations."""
    site = MonitoringSite(id=1, name="Test Site", url="https://example.com")
    ctx = CrawlContext(site=site, url="https://example.com")
    ctx.evidence_records = [
        {"id": i, "type": "evidence", "ocr_text": f"text_{i}"}
        for i in range(evidence_count)
    ]
    ctx.violations = [
        {"id": i, "type": "violation", "variant_name": f"variant_{i}"}
        for i in range(violation_count)
    ]
    return ctx


def _make_mock_session():
    """Create a mock DB session."""
    session = MagicMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.close = MagicMock()
    return session


# ------------------------------------------------------------------
# should_run (Req 12.5)
# ------------------------------------------------------------------


class TestShouldRun:
    def test_always_returns_true(self):
        """Req 12.5: should_run() は常に True。"""
        ctx = _make_ctx()
        plugin = DBStoragePlugin()
        assert plugin.should_run(ctx) is True

    def test_returns_true_even_with_empty_context(self):
        site = MonitoringSite(id=1, name="Test", url="https://example.com")
        ctx = CrawlContext(site=site, url="https://example.com")
        plugin = DBStoragePlugin()
        assert plugin.should_run(ctx) is True


# ------------------------------------------------------------------
# execute — individual INSERT (Req 20.1)
# ------------------------------------------------------------------


class TestIndividualInsert:
    @pytest.mark.asyncio
    async def test_uses_individual_insert_below_threshold(self):
        """Req 20.1: レコード数 ≤ 閾値で個別 INSERT。"""
        session = _make_mock_session()
        ctx = _make_ctx(evidence_count=3, violation_count=2)

        plugin = DBStoragePlugin(
            session_factory=lambda: session,
            bulk_threshold=10,
        )
        result = await plugin.execute(ctx)

        # Individual: add() called for each record
        assert session.add.call_count == 5
        session.add_all.assert_not_called()
        session.commit.assert_called_once()
        assert result.metadata["dbstorage_strategy"] == "individual"

    @pytest.mark.asyncio
    async def test_uses_individual_at_exact_threshold(self):
        """Req 20.1: レコード数 == 閾値で個別 INSERT。"""
        session = _make_mock_session()
        ctx = _make_ctx(evidence_count=5, violation_count=5)

        plugin = DBStoragePlugin(
            session_factory=lambda: session,
            bulk_threshold=10,
        )
        result = await plugin.execute(ctx)

        assert session.add.call_count == 10
        assert result.metadata["dbstorage_strategy"] == "individual"


# ------------------------------------------------------------------
# execute — bulk INSERT (Req 20.2)
# ------------------------------------------------------------------


class TestBulkInsert:
    @pytest.mark.asyncio
    async def test_uses_bulk_insert_above_threshold(self):
        """Req 20.2: レコード数 > 閾値でバルク INSERT。"""
        session = _make_mock_session()
        ctx = _make_ctx(evidence_count=8, violation_count=5)

        plugin = DBStoragePlugin(
            session_factory=lambda: session,
            bulk_threshold=10,
            bulk_batch_size=100,
        )
        result = await plugin.execute(ctx)

        # Bulk: add_all() called instead of individual add()
        session.add.assert_not_called()
        assert session.add_all.call_count >= 1
        session.commit.assert_called_once()
        assert result.metadata["dbstorage_strategy"] == "bulk"

    @pytest.mark.asyncio
    async def test_bulk_splits_into_batches(self):
        """Req 20.3: バッチサイズ上限で分割。"""
        session = _make_mock_session()
        ctx = _make_ctx(evidence_count=150, violation_count=100)

        plugin = DBStoragePlugin(
            session_factory=lambda: session,
            bulk_threshold=10,
            bulk_batch_size=100,
        )
        result = await plugin.execute(ctx)

        # 250 records / 100 batch size = 3 batches
        assert session.add_all.call_count == 3
        assert result.metadata["dbstorage_strategy"] == "bulk"
        assert result.metadata["dbstorage_bulk_batches"] == 3


# ------------------------------------------------------------------
# execute — transaction handling (Req 12.4, 20.4)
# ------------------------------------------------------------------


class TestTransactionHandling:
    @pytest.mark.asyncio
    async def test_single_transaction_commit(self):
        """Req 20.4: 単一トランザクションで実行。"""
        session = _make_mock_session()
        ctx = _make_ctx(evidence_count=3)

        plugin = DBStoragePlugin(session_factory=lambda: session, bulk_threshold=10)
        await plugin.execute(ctx)

        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_rollback_on_error(self):
        """Req 12.4: エラー時ロールバック。"""
        session = _make_mock_session()
        session.add.side_effect = Exception("DB write error")
        ctx = _make_ctx(evidence_count=1)

        plugin = DBStoragePlugin(session_factory=lambda: session, bulk_threshold=10)
        result = await plugin.execute(ctx)

        session.rollback.assert_called_once()
        assert len(result.errors) == 1
        assert "DB write error" in result.errors[0]["error"]

    @pytest.mark.asyncio
    async def test_rollback_on_bulk_error(self):
        session = _make_mock_session()
        session.add_all.side_effect = Exception("Bulk insert error")
        ctx = _make_ctx(evidence_count=15)

        plugin = DBStoragePlugin(
            session_factory=lambda: session,
            bulk_threshold=10,
        )
        result = await plugin.execute(ctx)

        session.rollback.assert_called_once()
        assert len(result.errors) == 1


# ------------------------------------------------------------------
# execute — no session factory
# ------------------------------------------------------------------


class TestNoSessionFactory:
    @pytest.mark.asyncio
    async def test_records_error_when_no_session(self):
        ctx = _make_ctx(evidence_count=1)
        plugin = DBStoragePlugin()
        result = await plugin.execute(ctx)

        assert len(result.errors) == 1
        assert "No database session" in result.errors[0]["error"]


# ------------------------------------------------------------------
# Threshold configuration (Req 20.5)
# ------------------------------------------------------------------


class TestThresholdConfiguration:
    def test_default_threshold(self):
        plugin = DBStoragePlugin()
        assert plugin.bulk_threshold == 10

    def test_custom_threshold(self):
        plugin = DBStoragePlugin(bulk_threshold=50)
        assert plugin.bulk_threshold == 50

    def test_env_threshold(self, monkeypatch):
        """Req 20.5: 環境変数で閾値設定。"""
        monkeypatch.setenv("DB_BULK_THRESHOLD", "25")
        plugin = DBStoragePlugin()
        assert plugin.bulk_threshold == 25


# ------------------------------------------------------------------
# Strategy selection helper
# ------------------------------------------------------------------


class TestStrategySelection:
    def test_individual_below_threshold(self):
        plugin = DBStoragePlugin(bulk_threshold=10)
        assert plugin.get_insert_strategy(5) == "individual"
        assert plugin.get_insert_strategy(10) == "individual"

    def test_bulk_above_threshold(self):
        plugin = DBStoragePlugin(bulk_threshold=10)
        assert plugin.get_insert_strategy(11) == "bulk"
        assert plugin.get_insert_strategy(100) == "bulk"

    def test_batch_count(self):
        plugin = DBStoragePlugin(bulk_threshold=10, bulk_batch_size=100)
        assert plugin.get_bulk_batch_count(5) == 0  # individual
        assert plugin.get_bulk_batch_count(100) == 1
        assert plugin.get_bulk_batch_count(250) == 3
        assert plugin.get_bulk_batch_count(101) == 2


# ------------------------------------------------------------------
# Metadata recording
# ------------------------------------------------------------------


class TestMetadataRecording:
    @pytest.mark.asyncio
    async def test_records_metadata(self):
        session = _make_mock_session()
        ctx = _make_ctx(evidence_count=3, violation_count=2)

        plugin = DBStoragePlugin(session_factory=lambda: session, bulk_threshold=10)
        result = await plugin.execute(ctx)

        assert result.metadata["dbstorage_strategy"] == "individual"
        assert result.metadata["dbstorage_total_records"] == 5
        assert result.metadata["dbstorage_evidence_count"] == 3
        assert result.metadata["dbstorage_violation_count"] == 2


# ------------------------------------------------------------------
# Plugin name
# ------------------------------------------------------------------


class TestPluginName:
    def test_name(self):
        plugin = DBStoragePlugin()
        assert plugin.name == "DBStoragePlugin"
