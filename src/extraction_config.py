"""
Configuration management for crawl data extraction features.

Loads feature flags and thresholds from environment variables.

Requirements: 24.1, 24.2, 24.3, 24.4, 24.5, 24.6
"""

import os


class ExtractionConfig:
    """Feature flags and settings for the extraction pipeline."""

    def __init__(self) -> None:
        # Feature flags (Req 24.1, 24.2)
        self.screenshot_enabled: bool = os.getenv(
            "SCREENSHOT_ENABLED", "true"
        ).lower() in ("true", "1", "yes")

        self.extraction_enabled: bool = os.getenv(
            "EXTRACTION_ENABLED", "true"
        ).lower() in ("true", "1", "yes")

        # Screenshot quality: "low", "medium", "high" (Req 24.3)
        self.screenshot_quality: str = os.getenv(
            "SCREENSHOT_QUALITY", "medium"
        ).lower()

        # Confidence score threshold (Req 24.4)
        self.confidence_threshold: float = float(
            os.getenv("CONFIDENCE_THRESHOLD", "0.5")
        )

        # Price change alert threshold percentage (Req 24.5)
        self.price_change_alert_threshold: float = float(
            os.getenv("PRICE_CHANGE_ALERT_THRESHOLD", "20.0")
        )

        # Screenshot timeout in seconds
        self.screenshot_timeout: int = int(
            os.getenv("SCREENSHOT_TIMEOUT", "10")
        )


# Module-level singleton for convenience
extraction_config = ExtractionConfig()
