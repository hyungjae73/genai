"""
Integration tests for Celery pipeline trace propagation.

Feature: production-readiness-improvements
Validates: Requirements 6.2, 6.3, 6.4

Verifies that:
- CeleryInstrumentor is called during instrument_celery
- Trace context headers are correctly injected and extracted
- inject/extract round-trip works with real OTel propagation
- instrument_celery respects OTEL_ENABLED=false
"""

import os
import pytest
from unittest.mock import patch, MagicMock

from opentelemetry import trace, context as otel_context
from opentelemetry.trace import SpanContext, TraceFlags, NonRecordingSpan

from src.core.telemetry import (
    instrument_celery,
    inject_trace_context,
    extract_trace_context,
)


class TestInstrumentCelery:
    """Tests for instrument_celery function."""

    @patch.dict(os.environ, {"OTEL_ENABLED": "true"})
    @patch("src.core.telemetry.init_telemetry")
    def test_instrument_celery_calls_celery_instrumentor(self, mock_init):
        """CeleryInstrumentor().instrument() is called when OTEL_ENABLED=true."""
        with patch(
            "opentelemetry.instrumentation.celery.CeleryInstrumentor"
        ) as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance

            instrument_celery("test-service")

            mock_instance.instrument.assert_called_once()
            mock_init.assert_called_once_with("test-service")

    @patch.dict(os.environ, {"OTEL_ENABLED": "false"})
    def test_instrument_celery_skips_when_disabled(self):
        """instrument_celery does nothing when OTEL_ENABLED=false."""
        with patch(
            "opentelemetry.instrumentation.celery.CeleryInstrumentor"
        ) as mock_cls:
            instrument_celery("test-service")
            mock_cls.assert_not_called()

    @patch.dict(os.environ, {"OTEL_ENABLED": "true"})
    @patch("src.core.telemetry.init_telemetry")
    def test_instrument_celery_without_service_name_skips_init(self, mock_init):
        """instrument_celery skips init_telemetry when service_name is None."""
        with patch(
            "opentelemetry.instrumentation.celery.CeleryInstrumentor"
        ) as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance

            instrument_celery(None)

            mock_instance.instrument.assert_called_once()
            mock_init.assert_not_called()


class TestTraceContextPropagation:
    """Integration tests for trace context injection and extraction."""

    def test_inject_adds_traceparent_header(self):
        """inject_trace_context adds a traceparent header to the dict."""
        span_context = SpanContext(
            trace_id=0x1234567890ABCDEF1234567890ABCDEF,
            span_id=0xFEDCBA0987654321,
            is_remote=False,
            trace_flags=TraceFlags(TraceFlags.SAMPLED),
        )
        span = NonRecordingSpan(span_context)
        ctx = trace.set_span_in_context(span)

        headers = {}
        token = otel_context.attach(ctx)
        try:
            result = inject_trace_context(headers)
        finally:
            otel_context.detach(token)

        assert "traceparent" in result
        assert result is headers  # same dict returned

    def test_extract_returns_context_with_correct_ids(self):
        """extract_trace_context returns context with matching trace/span IDs."""
        trace_id = 0xAABBCCDDEEFF00112233445566778899
        span_id = 0x1122334455667788

        span_context = SpanContext(
            trace_id=trace_id,
            span_id=span_id,
            is_remote=False,
            trace_flags=TraceFlags(TraceFlags.SAMPLED),
        )
        span = NonRecordingSpan(span_context)
        ctx = trace.set_span_in_context(span)

        headers = {}
        token = otel_context.attach(ctx)
        try:
            inject_trace_context(headers)
        finally:
            otel_context.detach(token)

        extracted_ctx = extract_trace_context(headers)
        extracted_span = trace.get_current_span(extracted_ctx)
        sc = extracted_span.get_span_context()

        assert sc.trace_id == trace_id
        assert sc.span_id == span_id

    def test_inject_on_empty_context_returns_headers_unchanged(self):
        """inject_trace_context with no active span returns headers (possibly empty)."""
        headers = {"existing-key": "value"}
        result = inject_trace_context(headers)
        assert result is headers
        assert "existing-key" in result

    def test_extract_with_no_traceparent_returns_context(self):
        """extract_trace_context with empty headers returns a valid context."""
        ctx = extract_trace_context({})
        assert ctx is not None
        # The span from an empty context should be invalid
        span = trace.get_current_span(ctx)
        sc = span.get_span_context()
        assert not sc.is_valid

    def test_full_pipeline_trace_propagation(self):
        """Simulates API → Celery task trace propagation across pipeline stages."""
        # API creates a root span context
        root_trace_id = 0xDEADBEEFCAFEBABE1234567890ABCDEF
        root_span_id = 0xCAFEBABEDEADBEEF

        root_sc = SpanContext(
            trace_id=root_trace_id,
            span_id=root_span_id,
            is_remote=False,
            trace_flags=TraceFlags(TraceFlags.SAMPLED),
        )
        root_span = NonRecordingSpan(root_sc)
        root_ctx = trace.set_span_in_context(root_span)

        # Stage 1: API injects context into task headers
        task_headers = {}
        token = otel_context.attach(root_ctx)
        try:
            inject_trace_context(task_headers)
        finally:
            otel_context.detach(token)

        # Stage 2: crawl-worker extracts context
        crawl_ctx = extract_trace_context(task_headers)
        crawl_span = trace.get_current_span(crawl_ctx)
        crawl_sc = crawl_span.get_span_context()

        assert crawl_sc.trace_id == root_trace_id, "crawl worker should share trace_id"

        # Stage 3: crawl-worker injects context for extract-worker
        extract_headers = {}
        token2 = otel_context.attach(crawl_ctx)
        try:
            inject_trace_context(extract_headers)
        finally:
            otel_context.detach(token2)

        # Stage 4: extract-worker extracts context
        extract_ctx = extract_trace_context(extract_headers)
        extract_span = trace.get_current_span(extract_ctx)
        extract_sc = extract_span.get_span_context()

        assert extract_sc.trace_id == root_trace_id, (
            "extract worker should share the same trace_id across pipeline"
        )
