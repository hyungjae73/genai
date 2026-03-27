"""
Error code system and structured logging for Payment Compliance Monitor.

Provides categorized error codes (PCM-E1xx through E7xx) with severity metadata,
rollback requirements, and a StructuredLogger for JSON-formatted log output.

Requirements: 10.1, 10.2
"""

import json
import os
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class Severity(str, Enum):
    """Error severity levels."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ErrorMeta:
    """Metadata for an error code."""

    def __init__(self, code: str, description: str, severity: Severity, requires_rollback: bool):
        self.code = code
        self.description = description
        self.severity = severity
        self.requires_rollback = requires_rollback


# ---------------------------------------------------------------------------
# PCM-E1xx: Infrastructure / Startup errors
# ---------------------------------------------------------------------------
PCM_E101 = ErrorMeta("PCM-E101", "Required environment variable not set", Severity.CRITICAL, False)
PCM_E102 = ErrorMeta("PCM-E102", "Port conflict", Severity.HIGH, False)
PCM_E103 = ErrorMeta("PCM-E103", "Docker image build failed", Severity.CRITICAL, False)
PCM_E104 = ErrorMeta("PCM-E104", "Container OOMKill", Severity.CRITICAL, True)
PCM_E105 = ErrorMeta("PCM-E105", "Disk space exhausted", Severity.CRITICAL, False)
PCM_E106 = ErrorMeta("PCM-E106", "Dependent service startup timeout", Severity.HIGH, False)
PCM_E107 = ErrorMeta("PCM-E107", "Production DEBUG override failed", Severity.CRITICAL, True)

# ---------------------------------------------------------------------------
# PCM-E2xx: Database errors
# ---------------------------------------------------------------------------
PCM_E201 = ErrorMeta("PCM-E201", "Database connection timeout", Severity.CRITICAL, True)
PCM_E202 = ErrorMeta("PCM-E202", "Migration failed", Severity.CRITICAL, True)
PCM_E203 = ErrorMeta("PCM-E203", "Database connection pool exhausted", Severity.HIGH, False)
PCM_E204 = ErrorMeta("PCM-E204", "Query timeout", Severity.MEDIUM, False)
PCM_E205 = ErrorMeta("PCM-E205", "Database authentication failed", Severity.CRITICAL, True)
PCM_E206 = ErrorMeta("PCM-E206", "Table/schema mismatch", Severity.CRITICAL, True)

# ---------------------------------------------------------------------------
# PCM-E3xx: Redis / Celery errors
# ---------------------------------------------------------------------------
PCM_E301 = ErrorMeta("PCM-E301", "Redis connection failed", Severity.HIGH, False)
PCM_E302 = ErrorMeta("PCM-E302", "Celery task timeout", Severity.MEDIUM, False)
PCM_E303 = ErrorMeta("PCM-E303", "Celery broker connection lost", Severity.HIGH, False)
PCM_E304 = ErrorMeta("PCM-E304", "Redis memory limit reached", Severity.HIGH, False)
PCM_E305 = ErrorMeta("PCM-E305", "Celery Beat duplicate schedule execution", Severity.MEDIUM, False)

# ---------------------------------------------------------------------------
# PCM-E4xx: Network / Communication errors
# ---------------------------------------------------------------------------
PCM_E401 = ErrorMeta("PCM-E401", "DNS resolution failed", Severity.CRITICAL, True)
PCM_E402 = ErrorMeta("PCM-E402", "Inter-service communication timeout", Severity.HIGH, False)
PCM_E403 = ErrorMeta("PCM-E403", "TLS/SSL certificate error", Severity.CRITICAL, True)
PCM_E404 = ErrorMeta("PCM-E404", "External API communication failed", Severity.LOW, False)
PCM_E405 = ErrorMeta("PCM-E405", "GHCR registry connection failed", Severity.HIGH, False)
PCM_E406 = ErrorMeta("PCM-E406", "Crawler target site connection failed", Severity.LOW, False)
PCM_E407 = ErrorMeta("PCM-E407", "Docker network partition", Severity.CRITICAL, True)

# ---------------------------------------------------------------------------
# PCM-E5xx: CI/CD Pipeline errors
# ---------------------------------------------------------------------------
PCM_E501 = ErrorMeta("PCM-E501", "Backend test failure", Severity.HIGH, False)
PCM_E502 = ErrorMeta("PCM-E502", "Frontend test failure", Severity.HIGH, False)
PCM_E503 = ErrorMeta("PCM-E503", "Docker image push failed", Severity.HIGH, False)
PCM_E504 = ErrorMeta("PCM-E504", "Security scan CRITICAL vulnerability detected", Severity.CRITICAL, False)
PCM_E505 = ErrorMeta("PCM-E505", "ECS deploy failed", Severity.CRITICAL, True)
PCM_E506 = ErrorMeta("PCM-E506", "ECS task launch failed", Severity.CRITICAL, True)
PCM_E507 = ErrorMeta("PCM-E507", "GitHub Actions OIDC authentication failed", Severity.CRITICAL, False)

# ---------------------------------------------------------------------------
# PCM-E6xx: Application errors
# ---------------------------------------------------------------------------
PCM_E601 = ErrorMeta("PCM-E601", "API error rate spike", Severity.HIGH, True)
PCM_E602 = ErrorMeta("PCM-E602", "Crawler consecutive failures", Severity.MEDIUM, False)
PCM_E603 = ErrorMeta("PCM-E603", "Data processing pipeline error", Severity.MEDIUM, False)

# ---------------------------------------------------------------------------
# PCM-E7xx: Security errors
# ---------------------------------------------------------------------------
PCM_E701 = ErrorMeta("PCM-E701", "DEBUG mode enabled in production", Severity.CRITICAL, True)
PCM_E702 = ErrorMeta("PCM-E702", "Secret leak detected", Severity.CRITICAL, False)
PCM_E703 = ErrorMeta("PCM-E703", "Invalid CORS origin", Severity.HIGH, True)


# ---------------------------------------------------------------------------
# Error code registry — lookup by code string
# ---------------------------------------------------------------------------
ERROR_REGISTRY: dict[str, ErrorMeta] = {
    meta.code: meta
    for name, meta in globals().items()
    if isinstance(meta, ErrorMeta)
}


def get_error_meta(code: str) -> Optional[ErrorMeta]:
    """Return the ErrorMeta for a given error code string, or None."""
    return ERROR_REGISTRY.get(code)


# ---------------------------------------------------------------------------
# StructuredLogger — JSON structured log output (Requirements 10.1, 10.2)
# ---------------------------------------------------------------------------
class StructuredLogger:
    """Outputs structured JSON log entries with error codes and metadata."""

    def __init__(self, service_name: str):
        self.service_name = service_name
        self.version = os.getenv("IMAGE_TAG", "dev")
        self.environment = os.getenv("ENVIRONMENT", "development")

    def log(self, level: str, error_code: str, message: str, **extra) -> dict:
        """Build and print a structured JSON log entry. Returns the dict."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "error_code": error_code,
            "service": self.service_name,
            "version": self.version,
            "environment": self.environment,
            "message": message,
        }
        # Attach severity / rollback metadata when available
        meta = get_error_meta(error_code)
        if meta is not None:
            entry["severity"] = meta.severity.value
            entry["requires_rollback"] = meta.requires_rollback
        entry.update(extra)
        print(json.dumps(entry))
        return entry

    # Convenience helpers
    def error(self, error_code: str, message: str, **extra) -> dict:
        return self.log("ERROR", error_code, message, **extra)

    def warning(self, error_code: str, message: str, **extra) -> dict:
        return self.log("WARNING", error_code, message, **extra)

    def info(self, error_code: str, message: str, **extra) -> dict:
        return self.log("INFO", error_code, message, **extra)
