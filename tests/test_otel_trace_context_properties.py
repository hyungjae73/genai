"""
Property-based tests for OpenTelemetry trace context inject/extract round-trip.

Feature: production-readiness-improvements
Property 3: OpenTelemetryトレースコンテキストの注入・抽出往復

Validates that inject_trace_context followed by extract_trace_context
preserves the original trace_id and span_id for any valid trace context.
"""

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st
from unittest.mock import patch

from opentelemetry import trace, context as otel_context
from opentelemetry.trace import SpanContext, TraceFlags, NonRecordingSpan

from src.core.telemetry import inject_trace_context, extract_trace_context


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# trace_id: 128-bit non-zero integer
trace_id_strategy = st.integers(min_value=1, max_value=(2**128) - 1)

# span_id: 64-bit non-zero integer
span_id_strategy = st.integers(min_value=1, max_value=(2**64) - 1)


# ===========================================================================
# Property 3: OpenTelemetryトレースコンテキストの注入・抽出往復
# ===========================================================================

class TestTraceContextInjectExtractRoundTrip:
    """
    Property 3: OpenTelemetryトレースコンテキストの注入・抽出往復

    For ANY valid trace context (random trace_id and span_id),
    inject_trace_context followed by extract_trace_context preserves
    the original trace_id and span_id.

    Feature: production-readiness-improvements, Property 3
    """

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    @given(
        tid=trace_id_strategy,
        sid=span_id_strategy,
    )
    def test_inject_extract_preserves_trace_id_and_span_id(self, tid: int, sid: int):
        """
        inject_trace_context then extract_trace_context preserves
        the original trace_id and span_id.

        **Validates: Requirements 6.2, 6.3**
        """
        # Create a SpanContext with the generated trace_id and span_id
        span_context = SpanContext(
            trace_id=tid,
            span_id=sid,
            is_remote=False,
            trace_flags=TraceFlags(TraceFlags.SAMPLED),
        )
        span = NonRecordingSpan(span_context)
        ctx = trace.set_span_in_context(span)

        # Inject trace context into headers under the generated context
        headers: dict = {}
        token = otel_context.attach(ctx)
        try:
            result_headers = inject_trace_context(headers)
        finally:
            otel_context.detach(token)

        # Verify traceparent header was injected
        assert "traceparent" in result_headers, (
            f"traceparent header not found in injected headers: {result_headers}"
        )

        # Extract trace context from headers
        extracted_ctx = extract_trace_context(result_headers)
        assert extracted_ctx is not None, "extract_trace_context returned None"

        # Get the span from the extracted context
        extracted_span = trace.get_current_span(extracted_ctx)
        extracted_sc = extracted_span.get_span_context()

        # Verify trace_id and span_id are preserved
        assert extracted_sc.trace_id == tid, (
            f"trace_id mismatch: expected {tid:#034x}, got {extracted_sc.trace_id:#034x}"
        )
        assert extracted_sc.span_id == sid, (
            f"span_id mismatch: expected {sid:#018x}, got {extracted_sc.span_id:#018x}"
        )

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    @given(
        tid=trace_id_strategy,
        sid=span_id_strategy,
    )
    def test_inject_produces_valid_traceparent_format(self, tid: int, sid: int):
        """
        inject_trace_context produces a traceparent header in the W3C format:
        version-trace_id-span_id-trace_flags (e.g., 00-<32hex>-<16hex>-01).

        **Validates: Requirements 6.2, 6.3**
        """
        span_context = SpanContext(
            trace_id=tid,
            span_id=sid,
            is_remote=False,
            trace_flags=TraceFlags(TraceFlags.SAMPLED),
        )
        span = NonRecordingSpan(span_context)
        ctx = trace.set_span_in_context(span)

        headers: dict = {}
        token = otel_context.attach(ctx)
        try:
            result_headers = inject_trace_context(headers)
        finally:
            otel_context.detach(token)

        traceparent = result_headers.get("traceparent", "")
        parts = traceparent.split("-")
        assert len(parts) == 4, (
            f"traceparent should have 4 parts, got {len(parts)}: {traceparent}"
        )
        assert parts[0] == "00", f"Version should be '00', got '{parts[0]}'"
        assert len(parts[1]) == 32, f"trace_id hex should be 32 chars, got {len(parts[1])}"
        assert len(parts[2]) == 16, f"span_id hex should be 16 chars, got {len(parts[2])}"

    @settings(
        max_examples=100,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    @given(
        tid=trace_id_strategy,
        sid=span_id_strategy,
    )
    def test_extract_returns_remote_span_context(self, tid: int, sid: int):
        """
        extract_trace_context returns a context whose span has is_remote=True,
        indicating it was propagated from another service.

        **Validates: Requirements 6.2, 6.3**
        """
        span_context = SpanContext(
            trace_id=tid,
            span_id=sid,
            is_remote=False,
            trace_flags=TraceFlags(TraceFlags.SAMPLED),
        )
        span = NonRecordingSpan(span_context)
        ctx = trace.set_span_in_context(span)

        headers: dict = {}
        token = otel_context.attach(ctx)
        try:
            inject_trace_context(headers)
        finally:
            otel_context.detach(token)

        extracted_ctx = extract_trace_context(headers)
        extracted_span = trace.get_current_span(extracted_ctx)
        extracted_sc = extracted_span.get_span_context()

        assert extracted_sc.is_remote is True, (
            "Extracted span context should be marked as remote"
        )
