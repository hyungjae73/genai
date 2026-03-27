"""
DBStoragePlugin — Reporter ステージ プラグイン。

パイプラインの実行結果を DB に保存する。
レコード数に応じて個別 INSERT とバルク INSERT を自動切替する。

Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 20.1, 20.2, 20.3, 20.4, 20.5
"""

from __future__ import annotations

import logging
import math
import os
from datetime import datetime, timezone
from typing import Any, Protocol

from src.pipeline.context import CrawlContext
from src.pipeline.plugin import CrawlPlugin

logger = logging.getLogger(__name__)

# Default threshold for switching between individual and bulk INSERT
DEFAULT_BULK_THRESHOLD = 10
DEFAULT_BULK_BATCH_SIZE = 100


class DBSession(Protocol):
    """Protocol for database session (dependency injection)."""

    def add(self, instance: Any) -> None: ...
    def add_all(self, instances: list[Any]) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
    def close(self) -> None: ...


class DBStoragePlugin(CrawlPlugin):
    """パイプライン実行結果を DB に保存するプラグイン。

    VerificationResult, EvidenceRecord, Violation を DB に保存する。
    レコード数 ≤ 閾値: 個別 INSERT
    レコード数 > 閾値: バルク INSERT（バッチサイズ上限で分割）

    Requirements: 12.1-12.5, 20.1-20.5
    """

    def __init__(
        self,
        session_factory=None,
        bulk_threshold: int | None = None,
        bulk_batch_size: int | None = None,
    ):
        """Initialize DBStoragePlugin.

        Args:
            session_factory: Optional callable() -> session for DB access.
                             Useful for dependency injection in tests.
            bulk_threshold: Override for DB_BULK_THRESHOLD. If None, reads from env.
            bulk_batch_size: Override for max bulk batch size. Defaults to 100.
        """
        self._session_factory = session_factory
        self._bulk_threshold = bulk_threshold
        self._bulk_batch_size = bulk_batch_size

    @property
    def bulk_threshold(self) -> int:
        """Get the bulk INSERT threshold."""
        if self._bulk_threshold is not None:
            return self._bulk_threshold
        return int(os.environ.get("DB_BULK_THRESHOLD", str(DEFAULT_BULK_THRESHOLD)))

    @property
    def bulk_batch_size(self) -> int:
        """Get the max bulk batch size."""
        if self._bulk_batch_size is not None:
            return self._bulk_batch_size
        return DEFAULT_BULK_BATCH_SIZE

    def should_run(self, ctx: CrawlContext) -> bool:
        """常に True を返す。"""
        return True

    async def execute(self, ctx: CrawlContext) -> CrawlContext:
        """パイプライン実行結果を DB に保存する。

        Args:
            ctx: パイプライン共有コンテキスト

        Returns:
            metadata に保存結果を追記した CrawlContext
        """
        session = None
        try:
            if self._session_factory is None:
                ctx.errors.append({
                    "plugin": self.name,
                    "stage": "reporter",
                    "error": "No database session factory configured",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                return ctx

            session = self._session_factory()

            # Collect all records to save
            evidence_records = ctx.evidence_records
            violations = ctx.violations
            total_records = len(evidence_records) + len(violations)

            # Determine INSERT strategy
            use_bulk = total_records > self.bulk_threshold
            strategy = "bulk" if use_bulk else "individual"

            try:
                if use_bulk:
                    self._bulk_insert(session, evidence_records, violations)
                else:
                    self._individual_insert(session, evidence_records, violations)

                session.commit()

                ctx.metadata["dbstorage_strategy"] = strategy
                ctx.metadata["dbstorage_total_records"] = total_records
                ctx.metadata["dbstorage_evidence_count"] = len(evidence_records)
                ctx.metadata["dbstorage_violation_count"] = len(violations)

                if use_bulk:
                    num_batches = math.ceil(total_records / self.bulk_batch_size) if total_records > 0 else 0
                    ctx.metadata["dbstorage_bulk_batches"] = num_batches

            except Exception as e:
                session.rollback()
                raise e

        except Exception as e:
            logger.error("DBStoragePlugin failed: %s", e)
            ctx.errors.append({
                "plugin": self.name,
                "stage": "reporter",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        finally:
            if session is not None:
                try:
                    session.close()
                except Exception:
                    pass

        return ctx

    def _individual_insert(
        self,
        session: Any,
        evidence_records: list[dict],
        violations: list[dict],
    ) -> None:
        """Insert records individually (for small record counts).

        Args:
            session: Database session
            evidence_records: Evidence records to insert
            violations: Violations to insert
        """
        for record in evidence_records:
            session.add(record)
        for violation in violations:
            session.add(violation)

    def _bulk_insert(
        self,
        session: Any,
        evidence_records: list[dict],
        violations: list[dict],
    ) -> None:
        """Insert records in bulk batches (for large record counts).

        Splits into batches of max bulk_batch_size.

        Args:
            session: Database session
            evidence_records: Evidence records to insert
            violations: Violations to insert
        """
        all_records = list(evidence_records) + list(violations)
        batch_size = self.bulk_batch_size

        for i in range(0, len(all_records), batch_size):
            batch = all_records[i:i + batch_size]
            session.add_all(batch)

    def get_insert_strategy(self, total_records: int) -> str:
        """Determine the INSERT strategy for a given record count.

        This is a public method for testing purposes.

        Args:
            total_records: Total number of records to insert

        Returns:
            "individual" or "bulk"
        """
        return "bulk" if total_records > self.bulk_threshold else "individual"

    def get_bulk_batch_count(self, total_records: int) -> int:
        """Calculate the number of bulk batches needed.

        Args:
            total_records: Total number of records

        Returns:
            Number of batches (0 if individual strategy)
        """
        if total_records <= self.bulk_threshold:
            return 0
        return math.ceil(total_records / self.bulk_batch_size)
