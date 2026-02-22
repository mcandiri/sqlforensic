"""Schema analyzer — extracts tables, columns, types, constraints, views, and overview."""

from __future__ import annotations

import logging
from typing import Any

from sqlforensic.connectors.base import BaseConnector

logger = logging.getLogger(__name__)


class SchemaAnalyzer:
    """Analyze database schema including tables, columns, views, and constraints.

    Extracts comprehensive metadata about every database object and
    provides a high-level overview of the schema composition.
    """

    def __init__(self, connector: BaseConnector) -> None:
        self.connector = connector

    def analyze(self) -> dict[str, Any]:
        """Run full schema analysis.

        Returns:
            Dict with keys: tables, views, stored_procedures, functions,
            indexes, overview.
        """
        logger.info("Starting schema analysis")

        tables = self._analyze_tables()
        views = self.connector.get_views()
        stored_procedures = self.connector.get_stored_procedures()
        functions = self.connector.get_functions()
        indexes = self.connector.get_indexes()
        foreign_keys = self.connector.get_foreign_keys()

        total_columns = sum(len(t.get("columns", [])) for t in tables)
        total_rows = sum(t.get("row_count", 0) or 0 for t in tables)

        overview = {
            "tables": len(tables),
            "views": len(views),
            "stored_procedures": len(stored_procedures),
            "functions": len(functions),
            "indexes": len(indexes),
            "foreign_keys": len(foreign_keys),
            "total_columns": total_columns,
            "total_rows": total_rows,
        }

        logger.info(
            "Schema analysis complete: %d tables, %d SPs, %d indexes",
            len(tables),
            len(stored_procedures),
            len(indexes),
        )

        return {
            "tables": tables,
            "views": views,
            "stored_procedures": stored_procedures,
            "functions": functions,
            "indexes": indexes,
            "foreign_keys": foreign_keys,
            "overview": overview,
        }

    def _analyze_tables(self) -> list[dict[str, Any]]:
        """Analyze all tables with their columns and constraints."""
        raw_tables = self.connector.get_tables()
        tables: list[dict[str, Any]] = []

        for raw in raw_tables:
            schema = raw.get("TABLE_SCHEMA", "dbo")
            name = raw.get("TABLE_NAME", "")
            row_count = raw.get("row_count", 0)

            columns = self.connector.get_columns(schema, name)

            has_pk = any(col.get("is_primary_key") for col in columns)

            tables.append(
                {
                    "TABLE_SCHEMA": schema,
                    "TABLE_NAME": name,
                    "row_count": row_count,
                    "columns": columns,
                    "column_count": len(columns),
                    "has_primary_key": has_pk,
                }
            )

        return tables
