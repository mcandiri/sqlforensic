"""Database health score calculator.

Computes an overall health score (0-100) based on weighted analysis
of schema quality, index coverage, dead code, and dependencies.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlforensic import AnalysisReport


class HealthScoreCalculator:
    """Calculate overall database health score from analysis results.

    Scoring starts at 100 and deducts points for various issues:
    - Tables without PK: -5 per table
    - Missing FK indexes: -2 per index
    - Dead procedures: -1 per SP
    - Tables without any index: -5 per table
    - Circular dependencies: -10 per cycle
    - High-complexity SPs: -2 per SP
    - Duplicate indexes: -2 per duplicate
    - Bonus points for good practices
    """

    def __init__(self, report: AnalysisReport) -> None:
        self.report = report
        self._issues: list[dict[str, Any]] = []

    def calculate(self) -> int:
        """Calculate and return health score (0-100)."""
        score = 100
        self._issues = []

        # Tables without primary key
        no_pk_tables = self._count_tables_without_pk()
        if no_pk_tables > 0:
            penalty = no_pk_tables * 5
            score -= penalty
            self._issues.append(
                {
                    "description": "Tables with no primary key",
                    "severity": "HIGH",
                    "count": no_pk_tables,
                    "penalty": penalty,
                    "category": "schema",
                }
            )

        # Missing foreign key indexes
        missing_fk_idx = len(self.report.missing_indexes)
        if missing_fk_idx > 0:
            penalty = min(missing_fk_idx * 2, 20)
            score -= penalty
            self._issues.append(
                {
                    "description": "Missing foreign key indexes",
                    "severity": "HIGH",
                    "count": missing_fk_idx,
                    "penalty": penalty,
                    "category": "indexes",
                }
            )

        # Dead procedures
        dead_sp_count = len(self.report.dead_procedures)
        if dead_sp_count > 0:
            penalty = min(dead_sp_count, 15)
            score -= penalty
            self._issues.append(
                {
                    "description": "Unused stored procedures",
                    "severity": "MEDIUM",
                    "count": dead_sp_count,
                    "penalty": penalty,
                    "category": "dead_code",
                }
            )

        # Tables without indexes
        no_idx_tables = self._count_tables_without_indexes()
        if no_idx_tables > 0:
            penalty = no_idx_tables * 5
            score -= penalty
            self._issues.append(
                {
                    "description": "Tables with no indexes",
                    "severity": "HIGH",
                    "count": no_idx_tables,
                    "penalty": penalty,
                    "category": "indexes",
                }
            )

        # Circular dependencies
        circular_count = len(self.report.circular_dependencies)
        if circular_count > 0:
            penalty = circular_count * 10
            score -= penalty
            self._issues.append(
                {
                    "description": "Circular dependencies detected",
                    "severity": "HIGH",
                    "count": circular_count,
                    "penalty": penalty,
                    "category": "dependencies",
                }
            )

        # High-complexity stored procedures
        complex_sps = [sp for sp in self.report.sp_analysis if sp.get("complexity_score", 0) > 50]
        if complex_sps:
            penalty = min(len(complex_sps) * 2, 15)
            score -= penalty
            self._issues.append(
                {
                    "description": "SPs with complexity score > 50",
                    "severity": "MEDIUM",
                    "count": len(complex_sps),
                    "penalty": penalty,
                    "category": "complexity",
                }
            )

        # Duplicate indexes
        dup_count = len(self.report.duplicate_indexes)
        if dup_count > 0:
            penalty = min(dup_count * 2, 10)
            score -= penalty
            self._issues.append(
                {
                    "description": "Duplicate indexes",
                    "severity": "MEDIUM",
                    "count": dup_count,
                    "penalty": penalty,
                    "category": "indexes",
                }
            )

        # Dead tables
        dead_table_count = len(self.report.dead_tables)
        if dead_table_count > 0:
            penalty = min(dead_table_count * 2, 10)
            score -= penalty
            self._issues.append(
                {
                    "description": "Tables with no relationships",
                    "severity": "MEDIUM",
                    "count": dead_table_count,
                    "penalty": penalty,
                    "category": "dead_code",
                }
            )

        # Empty tables
        empty_count = len(self.report.empty_tables)
        if empty_count > 0:
            penalty = min(empty_count, 5)
            score -= penalty
            self._issues.append(
                {
                    "description": "Empty tables (0 rows)",
                    "severity": "LOW",
                    "count": empty_count,
                    "penalty": penalty,
                    "category": "dead_code",
                }
            )

        # Security issues
        sec_count = len(self.report.security_issues)
        if sec_count > 0:
            penalty = min(sec_count * 3, 15)
            score -= penalty
            self._issues.append(
                {
                    "description": "Security concerns found",
                    "severity": "HIGH",
                    "count": sec_count,
                    "penalty": penalty,
                    "category": "security",
                }
            )

        return max(0, min(100, score))

    def get_issues(self) -> list[dict[str, Any]]:
        """Return list of identified issues (call after calculate())."""
        return sorted(self._issues, key=lambda x: x["penalty"], reverse=True)

    def _count_tables_without_pk(self) -> int:
        """Count tables that have no primary key."""
        count = 0
        for table in self.report.tables:
            columns = table.get("columns", [])
            has_pk = any(col.get("is_primary_key") for col in columns)
            if not has_pk and columns:
                count += 1
        return count

    def _count_tables_without_indexes(self) -> int:
        """Count tables that have zero indexes."""
        indexed_tables: set[str] = set()
        for idx in self.report.indexes:
            indexed_tables.add(idx.get("table_name", ""))

        count = 0
        for table in self.report.tables:
            name = table.get("TABLE_NAME", "")
            if name and name not in indexed_tables:
                count += 1
        return count
