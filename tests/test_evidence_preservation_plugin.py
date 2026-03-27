"""
Unit tests for EvidencePreservationPlugin.

Feature: crawl-pipeline-architecture
Validates: Requirements 11.1, 11.2, 11.3, 11.4
"""

import pytest

from src.models import MonitoringSite
from src.pipeline.context import CrawlContext
from src.pipeline.plugins.evidence_preservation_plugin import EvidencePreservationPlugin


def _make_ctx(evidence_records=None):
    """Helper to build a CrawlContext with evidence records."""
    site = MonitoringSite(id=1, name="Test Site", url="https://example.com")
    ctx = CrawlContext(site=site, url="https://example.com")
    if evidence_records:
        ctx.evidence_records = evidence_records
    return ctx


# ------------------------------------------------------------------
# should_run (Req 11.1)
# ------------------------------------------------------------------


class TestShouldRun:
    def test_returns_true_when_evidence_records_exist(self):
        ctx = _make_ctx(evidence_records=[{"ocr_text": "test"}])
        plugin = EvidencePreservationPlugin()
        assert plugin.should_run(ctx) is True

    def test_returns_false_when_no_evidence_records(self):
        ctx = _make_ctx()
        plugin = EvidencePreservationPlugin()
        assert plugin.should_run(ctx) is False

    def test_returns_false_when_empty_list(self):
        ctx = _make_ctx(evidence_records=[])
        plugin = EvidencePreservationPlugin()
        assert plugin.should_run(ctx) is False


# ------------------------------------------------------------------
# execute — evidence_type classification (Req 11.2)
# ------------------------------------------------------------------


class TestEvidenceTypeClassification:
    @pytest.mark.asyncio
    async def test_classifies_price_display(self):
        """Req 11.2: 価格表示を price_display に分類。"""
        ctx = _make_ctx(evidence_records=[
            {"ocr_text": "¥1,980 税込", "variant_name": "Default", "screenshot_path": "/tmp/s.png", "ocr_confidence": 0.95},
        ])
        plugin = EvidencePreservationPlugin(verification_result_id=100)
        result = await plugin.execute(ctx)

        assert result.evidence_records[0]["evidence_type"] == "price_display"

    @pytest.mark.asyncio
    async def test_classifies_terms_notice(self):
        ctx = _make_ctx(evidence_records=[
            {"ocr_text": "ご注意: 返品不可", "variant_name": "Default", "screenshot_path": "/tmp/s.png", "ocr_confidence": 0.9},
        ])
        plugin = EvidencePreservationPlugin(verification_result_id=100)
        result = await plugin.execute(ctx)

        assert result.evidence_records[0]["evidence_type"] == "terms_notice"

    @pytest.mark.asyncio
    async def test_classifies_subscription_condition(self):
        ctx = _make_ctx(evidence_records=[
            {"ocr_text": "定期購入 月額1,980円 自動更新", "variant_name": "Default", "screenshot_path": "/tmp/s.png", "ocr_confidence": 0.85},
        ])
        plugin = EvidencePreservationPlugin(verification_result_id=100)
        result = await plugin.execute(ctx)

        assert result.evidence_records[0]["evidence_type"] == "subscription_condition"

    @pytest.mark.asyncio
    async def test_classifies_general(self):
        ctx = _make_ctx(evidence_records=[
            {"ocr_text": "Some random text", "variant_name": "Default", "screenshot_path": "/tmp/s.png", "ocr_confidence": 0.7},
        ])
        plugin = EvidencePreservationPlugin(verification_result_id=100)
        result = await plugin.execute(ctx)

        assert result.evidence_records[0]["evidence_type"] == "general"

    @pytest.mark.asyncio
    async def test_empty_ocr_text_classifies_as_general(self):
        ctx = _make_ctx(evidence_records=[
            {"ocr_text": "", "variant_name": "Default", "screenshot_path": "/tmp/s.png", "ocr_confidence": 0.0},
        ])
        plugin = EvidencePreservationPlugin(verification_result_id=100)
        result = await plugin.execute(ctx)

        assert result.evidence_records[0]["evidence_type"] == "general"


# ------------------------------------------------------------------
# execute — required fields (Req 11.3)
# ------------------------------------------------------------------


class TestRequiredFields:
    @pytest.mark.asyncio
    async def test_all_required_fields_set(self):
        """Req 11.3: 全必須フィールドが設定される。"""
        ctx = _make_ctx(evidence_records=[
            {"ocr_text": "¥1,980", "variant_name": "A", "screenshot_path": "/tmp/a.png", "ocr_confidence": 0.95},
        ])
        plugin = EvidencePreservationPlugin(verification_result_id=42)
        result = await plugin.execute(ctx)

        record = result.evidence_records[0]
        assert record["verification_result_id"] == 42
        assert record["variant_name"] == "A"
        assert record["screenshot_path"] == "/tmp/a.png"
        assert record["ocr_text"] == "¥1,980"
        assert record["ocr_confidence"] == 0.95
        assert record["evidence_type"] is not None
        assert record["created_at"] is not None

    @pytest.mark.asyncio
    async def test_defaults_for_missing_fields(self):
        """Missing fields get sensible defaults."""
        ctx = _make_ctx(evidence_records=[{"ocr_text": "test"}])
        plugin = EvidencePreservationPlugin(verification_result_id=1)
        result = await plugin.execute(ctx)

        record = result.evidence_records[0]
        assert record["variant_name"] == "unknown"
        assert record["screenshot_path"] == ""
        assert record["ocr_confidence"] == 0.0


# ------------------------------------------------------------------
# execute — same verification_result_id (Req 11.4)
# ------------------------------------------------------------------


class TestSameVerificationResultId:
    @pytest.mark.asyncio
    async def test_all_records_share_same_id(self):
        """Req 11.4: 全レコードが同一 verification_result_id を持つ。"""
        ctx = _make_ctx(evidence_records=[
            {"ocr_text": "¥1,980", "variant_name": "A", "screenshot_path": "/a.png", "ocr_confidence": 0.9},
            {"ocr_text": "注意事項", "variant_name": "B", "screenshot_path": "/b.png", "ocr_confidence": 0.8},
            {"ocr_text": "定期購入", "variant_name": "C", "screenshot_path": "/c.png", "ocr_confidence": 0.7},
        ])
        plugin = EvidencePreservationPlugin(verification_result_id=99)
        result = await plugin.execute(ctx)

        ids = {r["verification_result_id"] for r in result.evidence_records}
        assert len(ids) == 1
        assert 99 in ids

    @pytest.mark.asyncio
    async def test_auto_generated_id_is_consistent(self):
        """Auto-generated ID is the same for all records in one run."""
        ctx = _make_ctx(evidence_records=[
            {"ocr_text": "A", "variant_name": "A", "screenshot_path": "/a.png", "ocr_confidence": 0.9},
            {"ocr_text": "B", "variant_name": "B", "screenshot_path": "/b.png", "ocr_confidence": 0.8},
        ])
        plugin = EvidencePreservationPlugin()  # No fixed ID
        result = await plugin.execute(ctx)

        ids = {r["verification_result_id"] for r in result.evidence_records}
        assert len(ids) == 1


# ------------------------------------------------------------------
# Field preservation
# ------------------------------------------------------------------


class TestFieldPreservation:
    @pytest.mark.asyncio
    async def test_preserves_existing_metadata(self):
        ctx = _make_ctx(evidence_records=[
            {"ocr_text": "test", "variant_name": "A", "screenshot_path": "/a.png", "ocr_confidence": 0.9},
        ])
        ctx.metadata["existing_key"] = "value"
        plugin = EvidencePreservationPlugin(verification_result_id=1)
        result = await plugin.execute(ctx)

        assert result.metadata["existing_key"] == "value"

    @pytest.mark.asyncio
    async def test_preserves_existing_errors(self):
        ctx = _make_ctx(evidence_records=[
            {"ocr_text": "test", "variant_name": "A", "screenshot_path": "/a.png", "ocr_confidence": 0.9},
        ])
        ctx.errors.append({"plugin": "other", "error": "previous"})
        plugin = EvidencePreservationPlugin(verification_result_id=1)
        result = await plugin.execute(ctx)

        assert result.errors[0]["plugin"] == "other"


# ------------------------------------------------------------------
# Plugin name
# ------------------------------------------------------------------


class TestPluginName:
    def test_name(self):
        plugin = EvidencePreservationPlugin()
        assert plugin.name == "EvidencePreservationPlugin"
