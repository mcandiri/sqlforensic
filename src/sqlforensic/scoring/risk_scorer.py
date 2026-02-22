"""Migration risk scorer for tables and stored procedures.

Calculates per-object risk scores to help teams understand the impact
of modifying database objects during migration or refactoring.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlforensic import AnalysisReport


class RiskScorer:
    """Calculate migration risk scores for tables and stored procedures.

    Risk is determined by:
    - Number of dependencies (SPs, views, other tables)
    - Complexity of dependent SPs
    - Centrality in the dependency graph
    - Row count (data volume impact)
    """

    def __init__(self, report: AnalysisReport) -> None:
        self.report = report

    def calculate(self) -> dict[str, Any]:
        """Calculate risk scores for all tables and SPs.

        Returns:
            Dict with 'tables' and 'procedures' keys containing risk info.
        """
        table_risks = self._calculate_table_risks()
        sp_risks = self._calculate_sp_risks()

        return {
            "tables": table_risks,
            "procedures": sp_risks,
        }

    def _calculate_table_risks(self) -> list[dict[str, Any]]:
        """Calculate risk score for each table."""
        risks: list[dict[str, Any]] = []

        # Build dependency map: table -> list of SPs that reference it
        table_sp_map: dict[str, list[str]] = {}
        for sp in self.report.sp_analysis:
            for table in sp.get("referenced_tables", []):
                table_sp_map.setdefault(table, []).append(sp.get("name", ""))

        for table in self.report.tables:
            table_name = table.get("TABLE_NAME", "")
            dependent_sps = table_sp_map.get(table_name, [])
            row_count = table.get("row_count", 0) or 0

            # FK dependencies (tables that reference this one)
            fk_deps = [
                rel
                for rel in self.report.relationships
                if rel.get("referenced_table") == table_name
            ]

            # Calculate score components
            dep_score = min(len(dependent_sps) * 5, 40)
            fk_score = min(len(fk_deps) * 5, 20)
            size_score = self._size_risk(row_count)

            # Complexity of dependent SPs
            complexity_score = 0
            for sp in self.report.sp_analysis:
                if sp.get("name") in dependent_sps:
                    complexity_score += sp.get("complexity_score", 0)
            complexity_score = min(complexity_score // 5, 20)

            total = min(dep_score + fk_score + size_score + complexity_score, 100)

            risks.append(
                {
                    "name": table_name,
                    "schema": table.get("TABLE_SCHEMA", ""),
                    "risk_score": total,
                    "risk_level": self._risk_level(total),
                    "dependent_sp_count": len(dependent_sps),
                    "dependent_sps": dependent_sps,
                    "fk_dependency_count": len(fk_deps),
                    "row_count": row_count,
                }
            )

        return sorted(risks, key=lambda x: x["risk_score"], reverse=True)

    def _calculate_sp_risks(self) -> list[dict[str, Any]]:
        """Calculate risk score for each stored procedure."""
        risks: list[dict[str, Any]] = []

        # Build reverse dependency: SP -> SPs that call it
        sp_callers: dict[str, list[str]] = {}
        for sp in self.report.sp_analysis:
            # This would require cross-reference data; simplified version
            sp_name = sp.get("name", "")
            sp_callers.setdefault(sp_name, [])

        for sp in self.report.sp_analysis:
            sp_name = sp.get("name", "")
            complexity = sp.get("complexity_score", 0)
            table_count = len(sp.get("referenced_tables", []))
            caller_count = len(sp_callers.get(sp_name, []))

            complexity_score = min(complexity, 40)
            dep_score = min(table_count * 5, 30)
            caller_score = min(caller_count * 10, 30)

            total = min(complexity_score + dep_score + caller_score, 100)

            risks.append(
                {
                    "name": sp_name,
                    "schema": sp.get("schema", ""),
                    "risk_score": total,
                    "risk_level": self._risk_level(total),
                    "complexity_score": complexity,
                    "referenced_table_count": table_count,
                    "caller_count": caller_count,
                }
            )

        return sorted(risks, key=lambda x: x["risk_score"], reverse=True)

    @staticmethod
    def _size_risk(row_count: int) -> int:
        """Calculate risk component from table size."""
        if row_count >= 10_000_000:
            return 20
        if row_count >= 1_000_000:
            return 15
        if row_count >= 100_000:
            return 10
        if row_count >= 10_000:
            return 5
        return 0

    @staticmethod
    def _risk_level(score: int) -> str:
        """Convert numeric risk score to label."""
        if score >= 80:
            return "CRITICAL"
        if score >= 60:
            return "HIGH"
        if score >= 40:
            return "MEDIUM"
        if score >= 20:
            return "LOW"
        return "MINIMAL"
