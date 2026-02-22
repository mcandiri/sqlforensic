"""Dead code analyzer — finds unused tables, SPs, orphan columns, and empty tables."""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class DeadCodeAnalyzer:
    """Detect dead code in the database: unused tables, SPs, and orphan columns.

    Works by cross-referencing tables, stored procedures, views, and
    foreign keys to find objects that are never referenced.
    """

    def __init__(
        self,
        tables: list[dict[str, Any]],
        stored_procedures: list[dict[str, Any]],
        foreign_keys: list[dict[str, Any]],
        views: list[dict[str, Any]],
    ) -> None:
        self.tables = tables
        self.stored_procedures = stored_procedures
        self.foreign_keys = foreign_keys
        self.views = views

    def analyze(self) -> dict[str, Any]:
        """Run dead code analysis.

        Returns:
            Dict with 'dead_procedures', 'dead_tables', 'orphan_columns',
            and 'empty_tables' keys.
        """
        logger.info("Starting dead code analysis")

        referenced_tables = self._find_referenced_tables()
        referenced_sps = self._find_referenced_sps()
        referenced_columns = self._find_referenced_columns()

        dead_tables = self._find_dead_tables(referenced_tables)
        dead_procedures = self._find_dead_procedures(referenced_sps)
        orphan_columns = self._find_orphan_columns(referenced_columns)
        empty_tables = self._find_empty_tables()

        logger.info(
            "Dead code analysis complete: %d dead tables, %d dead SPs, "
            "%d orphan columns, %d empty tables",
            len(dead_tables),
            len(dead_procedures),
            len(orphan_columns),
            len(empty_tables),
        )

        return {
            "dead_tables": dead_tables,
            "dead_procedures": dead_procedures,
            "orphan_columns": orphan_columns,
            "empty_tables": empty_tables,
        }

    def _find_referenced_tables(self) -> set[str]:
        """Find all tables referenced by FKs, SPs, or views."""
        referenced: set[str] = set()

        # Tables referenced by foreign keys
        for fk in self.foreign_keys:
            referenced.add(fk.get("parent_table", ""))
            referenced.add(fk.get("referenced_table", ""))

        # Tables referenced in SP bodies
        for sp in self.stored_procedures:
            body = sp.get("ROUTINE_DEFINITION") or ""
            for table in self.tables:
                table_name = table.get("TABLE_NAME", "")
                if table_name and re.search(rf"\b{re.escape(table_name)}\b", body, re.IGNORECASE):
                    referenced.add(table_name)

        # Tables referenced in view definitions
        for view in self.views:
            definition = view.get("VIEW_DEFINITION") or ""
            for table in self.tables:
                table_name = table.get("TABLE_NAME", "")
                if table_name and re.search(
                    rf"\b{re.escape(table_name)}\b", definition, re.IGNORECASE
                ):
                    referenced.add(table_name)

        return referenced

    def _find_referenced_sps(self) -> set[str]:
        """Find SPs that are called by other SPs."""
        referenced: set[str] = set()

        sp_names = {sp.get("ROUTINE_NAME", "") for sp in self.stored_procedures}

        for sp in self.stored_procedures:
            body = sp.get("ROUTINE_DEFINITION") or ""
            current_name = sp.get("ROUTINE_NAME", "")
            for name in sp_names:
                if (
                    name != current_name
                    and name
                    and re.search(rf"\b{re.escape(name)}\b", body, re.IGNORECASE)
                ):
                    referenced.add(name)

        return referenced

    def _find_referenced_columns(self) -> dict[str, set[str]]:
        """Find columns referenced in SPs and views, grouped by table."""
        referenced: dict[str, set[str]] = {}

        all_code = ""
        for sp in self.stored_procedures:
            all_code += (sp.get("ROUTINE_DEFINITION") or "") + "\n"
        for view in self.views:
            all_code += (view.get("VIEW_DEFINITION") or "") + "\n"

        for table in self.tables:
            table_name = table.get("TABLE_NAME", "")
            referenced[table_name] = set()
            for col in table.get("columns", []):
                col_name = col.get("COLUMN_NAME", "")
                if col_name and re.search(rf"\b{re.escape(col_name)}\b", all_code, re.IGNORECASE):
                    referenced[table_name].add(col_name)

        return referenced

    def _find_dead_tables(self, referenced: set[str]) -> list[dict[str, Any]]:
        """Find tables not referenced anywhere."""
        dead: list[dict[str, Any]] = []
        for table in self.tables:
            name = table.get("TABLE_NAME", "")
            if name and name not in referenced:
                dead.append(
                    {
                        "TABLE_SCHEMA": table.get("TABLE_SCHEMA", ""),
                        "TABLE_NAME": name,
                        "row_count": table.get("row_count", 0),
                        "column_count": table.get("column_count", 0),
                    }
                )
        return dead

    def _find_dead_procedures(self, referenced: set[str]) -> list[dict[str, Any]]:
        """Find stored procedures not called by other SPs."""
        dead: list[dict[str, Any]] = []
        for sp in self.stored_procedures:
            name = sp.get("ROUTINE_NAME", "")
            if name and name not in referenced:
                dead.append(
                    {
                        "ROUTINE_SCHEMA": sp.get("ROUTINE_SCHEMA", ""),
                        "ROUTINE_NAME": name,
                    }
                )
        return dead

    def _find_orphan_columns(self, referenced: dict[str, set[str]]) -> list[dict[str, Any]]:
        """Find columns not referenced in any SP or view."""
        orphans: list[dict[str, Any]] = []
        for table in self.tables:
            table_name = table.get("TABLE_NAME", "")
            ref_cols = referenced.get(table_name, set())
            for col in table.get("columns", []):
                col_name = col.get("COLUMN_NAME", "")
                # Skip primary keys — they're structural
                if col.get("is_primary_key"):
                    continue
                if col_name and col_name not in ref_cols:
                    orphans.append(
                        {
                            "table_name": table_name,
                            "column_name": col_name,
                            "data_type": col.get("DATA_TYPE", ""),
                        }
                    )
        return orphans

    def _find_empty_tables(self) -> list[dict[str, Any]]:
        """Find tables with zero rows."""
        empty: list[dict[str, Any]] = []
        for table in self.tables:
            row_count = table.get("row_count", 0) or 0
            if row_count == 0:
                empty.append(
                    {
                        "TABLE_SCHEMA": table.get("TABLE_SCHEMA", ""),
                        "TABLE_NAME": table.get("TABLE_NAME", ""),
                        "column_count": table.get("column_count", 0),
                    }
                )
        return empty
