"""Risk assessment for schema changes using dependency analysis."""

from __future__ import annotations

import re
from typing import Any

from sqlforensic.diff.diff_result import (
    DiffResult,
    RiskAssessment,
    TableModification,
)


class RiskAssessor:
    """Assess risk of schema changes using dependency graph data.

    Uses stored procedure bodies and foreign key relationships to determine
    how many objects each change will impact, and calculates a risk score.
    """

    def __init__(
        self,
        stored_procedures: list[dict[str, Any]],
        foreign_keys: list[dict[str, Any]],
        views: list[dict[str, Any]],
    ) -> None:
        self.stored_procedures = stored_procedures
        self.foreign_keys = foreign_keys
        self.views = views

    def assess(self, diff: DiffResult) -> list[RiskAssessment]:
        """Assess all changes in a DiffResult.

        Returns:
            List of RiskAssessment sorted by risk_score descending.
        """
        risks: list[RiskAssessment] = []

        # New tables — no risk
        for t in diff.tables.added_tables:
            risks.append(
                RiskAssessment(
                    change_description=f"ADD TABLE {t.schema}.{t.name}",
                    table=t.name,
                    risk_score=0.0,
                    risk_level="NONE",
                )
            )

        # Removed tables — high risk
        for t in diff.tables.removed_tables:
            affected = self._find_dependents(t.name)
            score = 0.5 + 0.15 * len(affected)
            risks.append(
                RiskAssessment(
                    change_description=f"DROP TABLE {t.schema}.{t.name}",
                    table=t.name,
                    risk_score=min(score, 1.0),
                    risk_level=self._score_to_level(score),
                    affected_objects=affected,
                    breaking_changes=[f"Table {t.name} will be permanently removed"],
                    recommendations=(
                        [f"Update {len(affected)} dependent objects BEFORE dropping {t.name}"]
                        if affected
                        else []
                    ),
                )
            )

        # Modified tables — assess each change
        for mod in diff.tables.modified_tables:
            risks.extend(self._assess_table_modification(mod))

        # Removed foreign keys — data integrity risk
        for fk in diff.foreign_keys_removed:
            risks.append(
                RiskAssessment(
                    change_description=(
                        f"DROP FK {fk.constraint_name} "
                        f"({fk.parent_table}.{fk.parent_column} "
                        f"→ {fk.referenced_table}.{fk.referenced_column})"
                    ),
                    table=fk.parent_table,
                    risk_score=0.15,
                    risk_level="LOW",
                    breaking_changes=["Foreign key constraint removed — data integrity risk"],
                )
            )

        # Added foreign keys — low risk
        for fk in diff.foreign_keys_added:
            risks.append(
                RiskAssessment(
                    change_description=(
                        f"ADD FK {fk.parent_table}.{fk.parent_column} "
                        f"→ {fk.referenced_table}.{fk.referenced_column}"
                    ),
                    table=fk.parent_table,
                    risk_score=0.1,
                    risk_level="NONE",
                    recommendations=[
                        "Ensure existing data satisfies the FK constraint before adding"
                    ],
                )
            )

        # Removed indexes — performance risk
        for idx in diff.indexes.removed_indexes:
            risks.append(
                RiskAssessment(
                    change_description=f"DROP INDEX {idx.index_name} ON {idx.table_name}",
                    table=idx.table_name,
                    risk_score=0.1,
                    risk_level="LOW",
                    breaking_changes=["Index removed — may impact query performance"],
                )
            )

        # Removed SPs
        for sp in diff.procedures.removed:
            name = sp.get("name", "")
            callers = self._find_sp_callers(name)
            score = 0.1 + 0.1 * len(callers)
            risks.append(
                RiskAssessment(
                    change_description=f"DROP PROCEDURE {sp.get('schema', '')}.{name}",
                    risk_score=min(score, 1.0),
                    risk_level=self._score_to_level(score),
                    affected_objects=callers,
                )
            )

        risks.sort(key=lambda r: r.risk_score, reverse=True)
        return risks

    def _assess_table_modification(self, mod: TableModification) -> list[RiskAssessment]:
        """Assess risk for all changes within a single table modification."""
        risks: list[RiskAssessment] = []
        dependents = self._find_dependents(mod.table_name)

        # Added columns (nullable) — almost no risk
        for col in mod.added_columns:
            score = 0.05 if col.is_nullable else 0.15
            risks.append(
                RiskAssessment(
                    change_description=f"ADD COLUMN {mod.table_name}.{col.name}",
                    table=mod.table_name,
                    risk_score=score,
                    risk_level=self._score_to_level(score),
                    recommendations=(
                        []
                        if col.is_nullable
                        else [
                            f"Adding NOT NULL column {col.name} requires a default "
                            f"or data update for existing rows"
                        ]
                    ),
                )
            )

        # Removed columns — risky
        for col in mod.removed_columns:
            col_dependents = self._find_column_dependents(mod.table_name, col.name)
            score = 0.3 + 0.1 * len(col_dependents)
            risks.append(
                RiskAssessment(
                    change_description=f"DROP COLUMN {mod.table_name}.{col.name}",
                    table=mod.table_name,
                    risk_score=min(score, 1.0),
                    risk_level=self._score_to_level(score),
                    affected_objects=col_dependents,
                    breaking_changes=[f"Column {col.name} will be permanently removed"],
                    recommendations=(
                        [
                            f"Update {len(col_dependents)} dependent objects "
                            f"BEFORE dropping {mod.table_name}.{col.name}"
                        ]
                        if col_dependents
                        else []
                    ),
                )
            )

        # Modified columns
        for col_mod in mod.modified_columns:
            score = self._score_column_change(col_mod.change_type, col_mod.is_breaking, dependents)
            detail = f"{col_mod.old_value} → {col_mod.new_value}"
            risks.append(
                RiskAssessment(
                    change_description=(
                        f"ALTER {mod.table_name}.{col_mod.column_name} "
                        f"({col_mod.change_type}: {detail})"
                    ),
                    table=mod.table_name,
                    risk_score=min(score, 1.0),
                    risk_level=self._score_to_level(score),
                    affected_objects=dependents if col_mod.is_breaking else [],
                    breaking_changes=(
                        [f"{col_mod.change_type}: {detail} may break existing data or queries"]
                        if col_mod.is_breaking
                        else []
                    ),
                )
            )

        return risks

    def _find_dependents(self, table_name: str) -> list[str]:
        """Find all SPs and views that reference a table."""
        dependents: list[str] = []
        for sp in self.stored_procedures:
            body = sp.get("ROUTINE_DEFINITION") or ""
            name = sp.get("ROUTINE_NAME", "")
            if table_name and re.search(rf"\b{re.escape(table_name)}\b", body, re.IGNORECASE):
                dependents.append(f"SP:{name}")
        for view in self.views:
            defn = view.get("VIEW_DEFINITION") or ""
            name = view.get("TABLE_NAME", "")
            if table_name and re.search(rf"\b{re.escape(table_name)}\b", defn, re.IGNORECASE):
                dependents.append(f"View:{name}")
        return dependents

    def _find_column_dependents(self, table_name: str, column_name: str) -> list[str]:
        """Find objects that reference a specific column."""
        dependents: list[str] = []
        for sp in self.stored_procedures:
            body = sp.get("ROUTINE_DEFINITION") or ""
            name = sp.get("ROUTINE_NAME", "")
            if (
                table_name
                and re.search(rf"\b{re.escape(table_name)}\b", body, re.IGNORECASE)
                and re.search(rf"\b{re.escape(column_name)}\b", body, re.IGNORECASE)
            ):
                dependents.append(f"SP:{name}")
        for view in self.views:
            defn = view.get("VIEW_DEFINITION") or ""
            name = view.get("TABLE_NAME", "")
            if (
                table_name
                and re.search(rf"\b{re.escape(table_name)}\b", defn, re.IGNORECASE)
                and re.search(rf"\b{re.escape(column_name)}\b", defn, re.IGNORECASE)
            ):
                dependents.append(f"View:{name}")
        return dependents

    def _find_sp_callers(self, sp_name: str) -> list[str]:
        """Find SPs that call a given SP."""
        callers: list[str] = []
        for sp in self.stored_procedures:
            body = sp.get("ROUTINE_DEFINITION") or ""
            name = sp.get("ROUTINE_NAME", "")
            if name != sp_name and re.search(rf"\b{re.escape(sp_name)}\b", body, re.IGNORECASE):
                callers.append(f"SP:{name}")
        return callers

    @staticmethod
    def _score_column_change(change_type: str, is_breaking: bool, dependents: list[str]) -> float:
        """Calculate risk score for a column modification."""
        base_scores = {
            "type_change": 0.2,
            "length_change": 0.15,
            "nullability_change": 0.2,
            "default_change": 0.05,
        }
        base = base_scores.get(change_type, 0.1)
        if is_breaking:
            base += 0.05 * len(dependents)
        return base

    @staticmethod
    def _score_to_level(score: float) -> str:
        """Convert numeric risk score to label."""
        if score >= 0.7:
            return "CRITICAL"
        if score >= 0.4:
            return "HIGH"
        if score >= 0.2:
            return "MEDIUM"
        if score >= 0.05:
            return "LOW"
        return "NONE"


def calculate_overall_risk(risks: list[RiskAssessment]) -> str:
    """Determine overall risk level from list of assessments."""
    if not risks:
        return "NONE"
    max_score = max(r.risk_score for r in risks)
    if max_score >= 0.7:
        return "CRITICAL"
    if max_score >= 0.4:
        return "HIGH"
    if max_score >= 0.2:
        return "MEDIUM"
    if max_score >= 0.05:
        return "LOW"
    return "NONE"
