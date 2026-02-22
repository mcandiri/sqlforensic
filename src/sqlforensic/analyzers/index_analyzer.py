"""Index analyzer — missing, unused, duplicate, and overlapping index detection."""

from __future__ import annotations

import logging
from typing import Any

from sqlforensic.connectors.base import BaseConnector
from sqlforensic.utils.formatting import build_create_index_sql, build_drop_index_sql

logger = logging.getLogger(__name__)


class IndexAnalyzer:
    """Analyze database indexes to find missing, unused, and duplicate indexes.

    Provides actionable recommendations with ready-to-run SQL statements.
    """

    def __init__(self, connector: BaseConnector) -> None:
        self.connector = connector

    def analyze(self) -> dict[str, Any]:
        """Run full index analysis.

        Returns:
            Dict with 'missing', 'unused', 'duplicates', 'overlapping',
            and 'recommendations' keys.
        """
        logger.info("Starting index analysis")

        all_indexes = self.connector.get_indexes()
        missing = self._analyze_missing()
        unused = self._find_unused(all_indexes)
        duplicates = self._find_duplicates(all_indexes)
        overlapping = self._find_overlapping(all_indexes)

        recommendations = self._generate_recommendations(missing, unused, duplicates)

        logger.info(
            "Index analysis complete: %d missing, %d unused, %d duplicates",
            len(missing),
            len(unused),
            len(duplicates),
        )

        return {
            "all": all_indexes,
            "missing": missing,
            "unused": unused,
            "duplicates": duplicates,
            "overlapping": overlapping,
            "recommendations": recommendations,
        }

    def _analyze_missing(self) -> list[dict[str, Any]]:
        """Find missing indexes from DMV recommendations."""
        raw = self.connector.get_missing_indexes()
        missing: list[dict[str, Any]] = []

        for row in raw:
            table_name = row.get("table_name", "")
            # Clean up table_name (may include schema prefix from DMV)
            if "." in table_name:
                parts = table_name.rsplit(".", 1)
                table_name = parts[-1].strip("[]")

            eq_cols = row.get("equality_columns") or ""
            ineq_cols = row.get("inequality_columns") or ""
            inc_cols = row.get("included_columns") or ""

            columns = [c.strip().strip("[]") for c in eq_cols.split(",") if c.strip()]
            columns += [c.strip().strip("[]") for c in ineq_cols.split(",") if c.strip()]
            include = [c.strip().strip("[]") for c in inc_cols.split(",") if c.strip()]

            if not columns:
                continue

            create_sql = build_create_index_sql(table_name, columns, include or None)

            missing.append(
                {
                    "table_name": table_name,
                    "equality_columns": eq_cols,
                    "inequality_columns": ineq_cols,
                    "included_columns": inc_cols,
                    "improvement_measure": row.get("improvement_measure", 0),
                    "user_seeks": row.get("user_seeks", 0),
                    "user_scans": row.get("user_scans", 0),
                    "create_sql": create_sql,
                }
            )

        return sorted(missing, key=lambda x: x["improvement_measure"], reverse=True)

    def _find_unused(self, indexes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Find indexes that have never been used for reads."""
        unused: list[dict[str, Any]] = []

        for idx in indexes:
            # Skip primary keys and unique constraints
            if idx.get("is_primary_key") or idx.get("is_unique"):
                continue

            seeks = idx.get("user_seeks") or 0
            scans = idx.get("user_scans") or 0
            lookups = idx.get("user_lookups") or 0

            if seeks == 0 and scans == 0 and lookups == 0:
                table_name = idx.get("table_name", "")
                index_name = idx.get("index_name", "")

                unused.append(
                    {
                        "table_name": table_name,
                        "index_name": index_name,
                        "index_type": idx.get("index_type", ""),
                        "columns": idx.get("columns", ""),
                        "user_updates": idx.get("user_updates", 0),
                        "drop_sql": build_drop_index_sql(table_name, index_name),
                    }
                )

        return unused

    def _find_duplicates(self, indexes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Find indexes that cover the exact same columns."""
        duplicates: list[dict[str, Any]] = []

        # Group indexes by table
        by_table: dict[str, list[dict[str, Any]]] = {}
        for idx in indexes:
            table = idx.get("table_name", "")
            by_table.setdefault(table, []).append(idx)

        for table, table_indexes in by_table.items():
            seen_columns: dict[str, str] = {}
            for idx in table_indexes:
                cols = idx.get("columns", "")
                if not cols:
                    continue

                # Normalize column list for comparison
                normalized = ",".join(c.strip().lower() for c in cols.split(","))

                if normalized in seen_columns:
                    duplicates.append(
                        {
                            "table_name": table,
                            "index_name": idx.get("index_name", ""),
                            "duplicate_of": seen_columns[normalized],
                            "columns": cols,
                            "drop_sql": build_drop_index_sql(table, idx.get("index_name", "")),
                        }
                    )
                else:
                    seen_columns[normalized] = idx.get("index_name", "")

        return duplicates

    def _find_overlapping(self, indexes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Find indexes where one is a prefix of another."""
        overlapping: list[dict[str, Any]] = []

        by_table: dict[str, list[dict[str, Any]]] = {}
        for idx in indexes:
            table = idx.get("table_name", "")
            by_table.setdefault(table, []).append(idx)

        for table, table_indexes in by_table.items():
            parsed: list[tuple[str, list[str]]] = []
            for idx in table_indexes:
                cols = idx.get("columns", "")
                if cols:
                    col_list = [c.strip().lower() for c in cols.split(",")]
                    parsed.append((idx.get("index_name", ""), col_list))

            for i, (name_a, cols_a) in enumerate(parsed):
                for j, (name_b, cols_b) in enumerate(parsed):
                    if i >= j:
                        continue
                    if cols_a == cols_b:
                        continue  # Already caught by duplicate detection

                    if len(cols_a) < len(cols_b) and cols_b[: len(cols_a)] == cols_a:
                        overlapping.append(
                            {
                                "table_name": table,
                                "shorter_index": name_a,
                                "longer_index": name_b,
                                "shorter_columns": ", ".join(cols_a),
                                "longer_columns": ", ".join(cols_b),
                            }
                        )
                    elif len(cols_b) < len(cols_a) and cols_a[: len(cols_b)] == cols_b:
                        overlapping.append(
                            {
                                "table_name": table,
                                "shorter_index": name_b,
                                "longer_index": name_a,
                                "shorter_columns": ", ".join(cols_b),
                                "longer_columns": ", ".join(cols_a),
                            }
                        )

        return overlapping

    def _generate_recommendations(
        self,
        missing: list[dict[str, Any]],
        unused: list[dict[str, Any]],
        duplicates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Generate prioritized index recommendations."""
        recs: list[dict[str, Any]] = []

        for idx in missing[:20]:
            recs.append(
                {
                    "action": "CREATE",
                    "priority": "HIGH",
                    "description": f"Create missing index on {idx['table_name']}",
                    "sql": idx["create_sql"],
                    "impact": idx.get("improvement_measure", 0),
                }
            )

        for idx in duplicates:
            recs.append(
                {
                    "action": "DROP",
                    "priority": "MEDIUM",
                    "description": (
                        f"Drop duplicate index {idx['index_name']} "
                        f"(duplicate of {idx['duplicate_of']})"
                    ),
                    "sql": idx["drop_sql"],
                    "impact": 0,
                }
            )

        for idx in unused:
            updates = idx.get("user_updates", 0) or 0
            if updates > 100:
                recs.append(
                    {
                        "action": "DROP",
                        "priority": "LOW",
                        "description": (
                            f"Consider dropping unused index {idx['index_name']} "
                            f"on {idx['table_name']} ({updates} writes, 0 reads)"
                        ),
                        "sql": idx["drop_sql"],
                        "impact": 0,
                    }
                )

        return recs
