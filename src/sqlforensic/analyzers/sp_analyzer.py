"""Stored procedure analyzer — complexity scoring and dependency extraction."""

from __future__ import annotations

import logging
from typing import Any

from sqlforensic.connectors.base import BaseConnector
from sqlforensic.parsers.sp_parser import SPParser

logger = logging.getLogger(__name__)


class SPAnalyzer:
    """Analyze stored procedures for complexity, dependencies, and anti-patterns.

    Parses each SP body to extract:
    - Complexity score and category
    - Referenced tables and CRUD operations
    - Anti-patterns (SELECT *, cursors, NOLOCK, etc.)
    - Parameter information
    """

    def __init__(
        self,
        connector: BaseConnector,
        stored_procedures: list[dict[str, Any]],
    ) -> None:
        self.connector = connector
        self.stored_procedures = stored_procedures
        self.parser = SPParser()

    def analyze(self) -> list[dict[str, Any]]:
        """Analyze all stored procedures.

        Returns:
            List of dicts with SP analysis results, sorted by complexity score.
        """
        logger.info("Starting stored procedure analysis (%d SPs)", len(self.stored_procedures))
        results: list[dict[str, Any]] = []

        for sp in self.stored_procedures:
            parsed = self.parser.parse(sp)

            results.append(
                {
                    "name": parsed.name,
                    "schema": parsed.schema,
                    "line_count": parsed.line_count,
                    "referenced_tables": parsed.referenced_tables,
                    "crud_operations": parsed.crud_operations,
                    "join_count": parsed.join_count,
                    "subquery_depth": parsed.subquery_depth,
                    "has_cursors": parsed.has_cursors,
                    "has_dynamic_sql": parsed.has_dynamic_sql,
                    "has_temp_tables": parsed.has_temp_tables,
                    "case_count": parsed.case_count,
                    "complexity_score": parsed.complexity_score,
                    "complexity_category": parsed.complexity_category,
                    "anti_patterns": parsed.anti_patterns,
                    "parameters": parsed.parameters,
                }
            )

        results.sort(key=lambda x: x["complexity_score"], reverse=True)
        logger.info("SP analysis complete")
        return results
