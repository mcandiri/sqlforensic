"""Relationship analyzer — discovers FK and implicit relationships."""

from __future__ import annotations

import logging
import re
from typing import Any

from sqlforensic.connectors.base import BaseConnector
from sqlforensic.utils.sql_patterns import FK_NAMING_PATTERN

logger = logging.getLogger(__name__)


class RelationshipAnalyzer:
    """Discover explicit and implicit relationships between tables.

    Finds three types of relationships:
    - Explicit: Foreign key constraints (confidence: 100%)
    - SP-based: Table joins found in stored procedure code (confidence: 80%)
    - Naming-based: Column naming conventions like StudentId -> Students (confidence: 60%)
    """

    def __init__(
        self,
        connector: BaseConnector,
        tables: list[dict[str, Any]],
        stored_procedures: list[dict[str, Any]],
    ) -> None:
        self.connector = connector
        self.tables = tables
        self.stored_procedures = stored_procedures
        self._table_names: set[str] = {t.get("TABLE_NAME", "") for t in tables}

    def analyze(self) -> dict[str, Any]:
        """Discover all relationships.

        Returns:
            Dict with 'explicit' (FK) and 'implicit' (SP + naming based) lists.
        """
        logger.info("Starting relationship analysis")

        explicit = self.connector.get_foreign_keys()
        implicit: list[dict[str, Any]] = []

        # SP-based implicit relationships
        sp_rels = self._discover_sp_relationships()
        implicit.extend(sp_rels)

        # Naming convention-based relationships
        naming_rels = self._discover_naming_relationships()
        implicit.extend(naming_rels)

        # Deduplicate implicit relationships
        implicit = self._deduplicate(implicit, explicit)

        logger.info(
            "Relationship analysis complete: %d explicit, %d implicit",
            len(explicit),
            len(implicit),
        )

        return {
            "explicit": explicit,
            "implicit": implicit,
        }

    def _discover_sp_relationships(self) -> list[dict[str, Any]]:
        """Find implicit relationships from JOIN patterns in stored procedures."""
        relationships: list[dict[str, Any]] = []
        join_pattern = re.compile(
            r"(\w+)\s+(?:\w+\s+)?JOIN\s+(\w+)\s+(?:\w+\s+)?ON\s+"
            r"(?:\w+\.)?(\w+)\s*=\s*(?:\w+\.)?(\w+)",
            re.IGNORECASE,
        )

        seen: set[tuple[str, str]] = set()

        for sp in self.stored_procedures:
            body = sp.get("ROUTINE_DEFINITION") or ""
            if not body:
                continue

            for match in join_pattern.finditer(body):
                table_a = match.group(1).strip('[]"')
                table_b = match.group(2).strip('[]"')
                col_a = match.group(3)
                col_b = match.group(4)

                if table_a not in self._table_names or table_b not in self._table_names:
                    continue

                key = (min(table_a, table_b), max(table_a, table_b))
                if key in seen:
                    continue
                seen.add(key)

                relationships.append(
                    {
                        "parent_table": table_a,
                        "parent_column": col_a,
                        "referenced_table": table_b,
                        "referenced_column": col_b,
                        "confidence": 80,
                        "source": "stored_procedure",
                        "source_name": sp.get("ROUTINE_NAME", ""),
                    }
                )

        return relationships

    def _discover_naming_relationships(self) -> list[dict[str, Any]]:
        """Find implicit relationships from column naming conventions."""
        relationships: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()

        # Build a lookup: table name (lowercase) -> actual table name
        table_lookup: dict[str, str] = {}
        for name in self._table_names:
            table_lookup[name.lower()] = name
            # Also try plural forms
            if name.lower().endswith("s"):
                table_lookup[name.lower()] = name
            else:
                table_lookup[name.lower() + "s"] = name

        for table in self.tables:
            table_name = table.get("TABLE_NAME", "")
            for col in table.get("columns", []):
                col_name = col.get("COLUMN_NAME", "")
                match = re.match(FK_NAMING_PATTERN, col_name)
                if not match:
                    continue

                ref_base = match.group(1).lower()
                # Try direct match, plural, and common suffixes
                candidates = [ref_base, ref_base + "s", ref_base + "es"]

                for candidate in candidates:
                    if candidate in table_lookup:
                        ref_table = table_lookup[candidate]
                        if ref_table == table_name:
                            continue

                        key = (table_name, col_name, ref_table)
                        if key in seen:
                            continue
                        seen.add(key)

                        relationships.append(
                            {
                                "parent_table": table_name,
                                "parent_column": col_name,
                                "referenced_table": ref_table,
                                "referenced_column": "Id",
                                "confidence": 60,
                                "source": "naming_convention",
                                "source_name": f"{col_name} -> {ref_table}",
                            }
                        )
                        break

        return relationships

    def _deduplicate(
        self,
        implicit: list[dict[str, Any]],
        explicit: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Remove implicit relationships that duplicate explicit FKs."""
        explicit_pairs: set[tuple[str, str]] = set()
        for fk in explicit:
            pair = (
                fk.get("parent_table", ""),
                fk.get("referenced_table", ""),
            )
            explicit_pairs.add(pair)
            explicit_pairs.add((pair[1], pair[0]))  # Both directions

        return [
            rel
            for rel in implicit
            if (rel["parent_table"], rel["referenced_table"]) not in explicit_pairs
        ]
