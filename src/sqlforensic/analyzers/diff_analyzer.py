"""Diff analyzer — orchestrates full schema comparison between two databases."""

from __future__ import annotations

import logging
from typing import Any

from sqlforensic.analyzers.schema_analyzer import SchemaAnalyzer
from sqlforensic.connectors.base import BaseConnector
from sqlforensic.diff.diff_result import DiffResult
from sqlforensic.diff.index_differ import diff_indexes
from sqlforensic.diff.risk_assessor import RiskAssessor, calculate_overall_risk
from sqlforensic.diff.schema_differ import diff_foreign_keys, diff_tables
from sqlforensic.diff.sp_differ import diff_functions, diff_procedures, diff_views

logger = logging.getLogger(__name__)


class DiffAnalyzer:
    """Orchestrate a full schema diff between a source and target database.

    Connects to both databases via their connectors, extracts schemas using
    :class:`SchemaAnalyzer`, runs table/column/SP/index/FK diffs, assesses
    risk, and assembles a complete :class:`DiffResult`.

    Args:
        source_connector: Connector to the source (desired-state) database.
        target_connector: Connector to the target (current-state) database.
        include_data: When True, compare row counts between source and target.
        schema_only: When True, skip stored procedure / view / function diffs.
    """

    def __init__(
        self,
        source_connector: BaseConnector,
        target_connector: BaseConnector,
        include_data: bool = False,
        schema_only: bool = False,
    ) -> None:
        self.source_connector = source_connector
        self.target_connector = target_connector
        self.include_data = include_data
        self.schema_only = schema_only

    def analyze(self) -> DiffResult:
        """Run the full schema diff between source and target.

        Steps:
            1. Use SchemaAnalyzer on both connectors to fetch tables, views,
               stored procedures, functions, and indexes.
            2. Retrieve foreign keys from both databases.
            3. Run schema_differ.diff_tables().
            4. Run sp_differ.diff_procedures(), diff_views(), diff_functions()
               (unless schema_only is True).
            5. Run index_differ.diff_indexes().
            6. Run schema_differ.diff_foreign_keys().
            7. Run RiskAssessor.assess() and calculate_overall_risk().
            8. If include_data, compare row counts.
            9. Assemble and return DiffResult.

        Returns:
            A fully populated DiffResult.
        """
        logger.info(
            "Starting diff analysis (include_data=%s, schema_only=%s)",
            self.include_data,
            self.schema_only,
        )

        # Step 1 — Analyze both schemas
        logger.info("Analyzing source schema")
        source_schema = SchemaAnalyzer(self.source_connector).analyze()

        logger.info("Analyzing target schema")
        target_schema = SchemaAnalyzer(self.target_connector).analyze()

        source_tables: list[dict[str, Any]] = source_schema["tables"]
        target_tables: list[dict[str, Any]] = target_schema["tables"]
        source_views: list[dict[str, Any]] = source_schema["views"]
        target_views: list[dict[str, Any]] = target_schema["views"]
        source_sps: list[dict[str, Any]] = source_schema["stored_procedures"]
        target_sps: list[dict[str, Any]] = target_schema["stored_procedures"]
        source_funcs: list[dict[str, Any]] = source_schema["functions"]
        target_funcs: list[dict[str, Any]] = target_schema["functions"]
        source_indexes: list[dict[str, Any]] = source_schema["indexes"]
        target_indexes: list[dict[str, Any]] = target_schema["indexes"]

        # Step 2 — Foreign keys
        source_fks: list[dict[str, Any]] = source_schema["foreign_keys"]
        target_fks: list[dict[str, Any]] = target_schema["foreign_keys"]

        # Step 3 — Table / column diff
        logger.info("Diffing tables and columns")
        table_diff = diff_tables(source_tables, target_tables)

        # Step 4 — Programmable object diffs (unless schema_only)
        if self.schema_only:
            logger.info("Skipping programmable object diffs (schema_only=True)")
            proc_diff = diff_procedures([], [])
            view_diff = diff_views([], [])
            func_diff = diff_functions([], [])
        else:
            logger.info("Diffing stored procedures, views, and functions")
            proc_diff = diff_procedures(source_sps, target_sps)
            view_diff = diff_views(source_views, target_views)
            func_diff = diff_functions(source_funcs, target_funcs)

        # Step 5 — Index diff
        logger.info("Diffing indexes")
        index_diff = diff_indexes(source_indexes, target_indexes)

        # Step 6 — Foreign key diff
        logger.info("Diffing foreign keys")
        fks_added, fks_removed = diff_foreign_keys(source_fks, target_fks)

        # Step 7 — Assemble partial result for risk assessment
        result = DiffResult(
            source_database=self.source_connector.config.database,
            target_database=self.target_connector.config.database,
            source_server=self.source_connector.config.server,
            target_server=self.target_connector.config.server,
            provider=self.source_connector.config.provider,
            tables=table_diff,
            indexes=index_diff,
            procedures=proc_diff,
            views=view_diff,
            functions=func_diff,
            foreign_keys_added=fks_added,
            foreign_keys_removed=fks_removed,
            include_data=self.include_data,
        )

        # Risk assessment
        logger.info("Running risk assessment")
        assessor = RiskAssessor(
            stored_procedures=target_sps,
            foreign_keys=target_fks,
            views=target_views,
        )
        risks = assessor.assess(result)
        result.risks = risks
        result.risk_level = calculate_overall_risk(risks)

        # Propagate per-table risk scores from assessments
        self._apply_table_risk_scores(result)

        # Step 8 — Row count comparison
        if self.include_data:
            logger.info("Comparing row counts")
            result.row_count_changes = self._compare_row_counts(source_tables, target_tables)

        logger.info(
            "Diff analysis complete: %d total changes, risk=%s",
            result.total_changes,
            result.risk_level,
        )

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compare_row_counts(
        source_tables: list[dict[str, Any]],
        target_tables: list[dict[str, Any]],
    ) -> list[dict[str, int | str]]:
        """Compare row counts for tables present in both databases.

        Returns:
            List of dicts with table name, source count, target count,
            and the delta.
        """
        source_map = {
            f"{t.get('TABLE_SCHEMA', 'dbo')}.{t.get('TABLE_NAME', '')}": t for t in source_tables
        }
        target_map = {
            f"{t.get('TABLE_SCHEMA', 'dbo')}.{t.get('TABLE_NAME', '')}": t for t in target_tables
        }

        changes: list[dict[str, int | str]] = []
        for key in sorted(set(source_map.keys()) & set(target_map.keys())):
            src_count = source_map[key].get("row_count", 0) or 0
            tgt_count = target_map[key].get("row_count", 0) or 0
            if src_count != tgt_count:
                changes.append(
                    {
                        "table": key,
                        "source_rows": src_count,
                        "target_rows": tgt_count,
                        "delta": src_count - tgt_count,
                    }
                )

        return changes

    @staticmethod
    def _apply_table_risk_scores(result: DiffResult) -> None:
        """Propagate risk scores from assessments to modified tables.

        For each modified table, find all risk assessments targeting that
        table and set the table's risk_score to the maximum, collecting
        all risk details.
        """
        for mod in result.tables.modified_tables:
            table_risks = [r for r in result.risks if r.table == mod.table_name]
            if table_risks:
                mod.risk_score = max(r.risk_score for r in table_risks)
                mod.risk_details = [
                    f"[{r.risk_level}] {r.change_description}"
                    for r in table_risks
                    if r.risk_level not in ("NONE",)
                ]
