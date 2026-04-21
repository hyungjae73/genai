"""OpenTelemetry telemetry initialization and instrumentation."""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def init_telemetry(service_name: Optional[str] = None) -> None:
    """Initialize OpenTelemetry TracerProvider with BatchSpanProcessor + OTLP exporter.

    Environment variables:
        OTEL_ENABLED: "true" (default) / "false"
        OTEL_EXPORTER_OTLP_ENDPOINT: OTLP endpoint (default: http://localhost:4317)
        OTEL_SERVICE_NAME: Service name (default: payment-compliance-api)
    """
    if os.getenv("OTEL_ENABLED", "true").lower() == "false":
        logger.info("OpenTelemetry disabled (OTEL_ENABLED=false)")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME

        svc_name = service_name or os.getenv("OTEL_SERVICE_NAME", "payment-compliance-api")
        endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

        resource = Resource.create({SERVICE_NAME: svc_name})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        logger.info("OpenTelemetry initialized: service=%s, endpoint=%s", svc_name, endpoint)
    except ImportError:
        logger.warning("OpenTelemetry packages not installed, skipping initialization")
    except Exception as e:
        logger.warning("OpenTelemetry initialization failed: %s", e)


def instrument_fastapi(app) -> None:
    """Instrument FastAPI + SQLAlchemy + HTTPX with OpenTelemetry."""
    if os.getenv("OTEL_ENABLED", "true").lower() == "false":
        return

    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI instrumented with OpenTelemetry")
    except ImportError:
        logger.debug("opentelemetry-instrumentation-fastapi not installed")
    except Exception as e:
        logger.warning("FastAPI instrumentation failed: %s", e)

    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from src.database import async_engine
        SQLAlchemyInstrumentor().instrument(engine=async_engine.sync_engine)
        logger.info("SQLAlchemy instrumented with OpenTelemetry")
    except ImportError:
        logger.debug("opentelemetry-instrumentation-sqlalchemy not installed")
    except Exception as e:
        logger.warning("SQLAlchemy instrumentation failed: %s", e)

    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        HTTPXClientInstrumentor().instrument()
        logger.info("HTTPX instrumented with OpenTelemetry")
    except ImportError:
        logger.debug("opentelemetry-instrumentation-httpx not installed")
    except Exception as e:
        logger.warning("HTTPX instrumentation failed: %s", e)


def instrument_celery(service_name: Optional[str] = None) -> None:
    """Instrument Celery with OpenTelemetry for distributed trace propagation.

    Uses CeleryInstrumentor to automatically create spans for each task execution
    and propagate trace context across task boundaries.

    Args:
        service_name: Optional service name to initialize telemetry with.
    """
    if os.getenv("OTEL_ENABLED", "true").lower() == "false":
        return
    try:
        from opentelemetry.instrumentation.celery import CeleryInstrumentor
        CeleryInstrumentor().instrument()
        if service_name:
            init_telemetry(service_name)
        logger.info("Celery instrumented with OpenTelemetry: service=%s", service_name)
    except ImportError:
        logger.debug("opentelemetry-instrumentation-celery not installed")
    except Exception as e:
        logger.warning("Celery instrumentation failed: %s", e)


def inject_trace_context(headers: dict) -> dict:
    """Inject current span context into Celery task headers.

    Uses the OpenTelemetry propagation API to inject the current trace context
    (traceparent, tracestate) into the provided headers dict.

    Args:
        headers: Mutable dict to inject trace context into.

    Returns:
        The same headers dict with trace context injected.
    """
    try:
        from opentelemetry.propagate import inject
        inject(headers)
    except ImportError:
        pass
    except Exception:
        pass
    return headers


def extract_trace_context(headers: dict):
    """Extract span context from Celery task headers.

    Uses the OpenTelemetry propagation API to extract trace context
    from the provided headers dict.

    Args:
        headers: Dict containing trace context headers (traceparent, tracestate).

    Returns:
        An OpenTelemetry Context object, or None if extraction fails.
    """
    try:
        from opentelemetry.propagate import extract
        return extract(headers)
    except ImportError:
        return None
    except Exception:
        return None
