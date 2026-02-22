"""Size analyzer — table sizes, row counts, and space usage."""

from __future__ import annotations

import logging
from typing import Any

from sqlforensic.connectors.base import BaseConnector

logger = logging.getLogger(__name__)


class SizeAnalyzer:
    """Analyze table sizes, row counts, and storage usage.

    Provides insights into data distribution and identifies
    unusually large or growing tables.
    """

    def __init__(self, connector: BaseConnector) -> None:
        self.connector = connector

    def analyze(self) -> list[dict[str, Any]]:
        """Run size analysis.

        Returns:
            List of dicts with table size information, sorted by total space.
        """
        logger.info("Starting size analysis")

        raw = self.connector.get_table_sizes()
        results: list[dict[str, Any]] = []

        for row in raw:
            total_kb = row.get("total_space_kb", 0) or 0
            used_kb = row.get("used_space_kb", 0) or 0
            row_count = row.get("row_count", 0) or 0

            avg_row_size = (used_kb * 1024 / row_count) if row_count > 0 else 0

            results.append(
                {
                    "table_schema": row.get("table_schema", ""),
                    "table_name": row.get("table_name", ""),
                    "row_count": row_count,
                    "total_space_kb": total_kb,
                    "used_space_kb": used_kb,
                    "unused_space_kb": total_kb - used_kb,
                    "avg_row_size_bytes": round(avg_row_size, 1),
                }
            )

        logger.info("Size analysis complete: %d tables analyzed", len(results))
        return sorted(results, key=lambda x: x["total_space_kb"], reverse=True)
