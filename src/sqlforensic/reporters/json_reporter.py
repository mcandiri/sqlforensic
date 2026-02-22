"""JSON report exporter."""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING

from sqlforensic import __version__

if TYPE_CHECKING:
    from sqlforensic import AnalysisReport


class JSONReporter:
    """Export analysis results as machine-readable JSON.

    Produces a structured JSON file suitable for CI/CD pipelines,
    dashboards, or further processing.
    """

    def __init__(self, report: AnalysisReport) -> None:
        self.report = report

    def export(self, output_path: str) -> None:
        """Export report to JSON file.

        Args:
            output_path: Path to write the JSON file.
        """
        data = {
            "metadata": {
                "tool": "SQLForensic",
                "version": __version__,
                "generated_at": datetime.now().isoformat(),
                "database": self.report.database,
                "provider": self.report.provider,
            },
            "health_score": self.report.health_score,
            "schema_overview": self.report.schema_overview,
            "tables": self.report.tables,
            "views": self.report.views,
            "stored_procedures": [
                {k: v for k, v in sp.items() if k != "ROUTINE_DEFINITION"}
                for sp in self.report.stored_procedures
            ],
            "relationships": {
                "explicit": self.report.relationships,
                "implicit": self.report.implicit_relationships,
            },
            "indexes": {
                "missing": self.report.missing_indexes,
                "unused": self.report.unused_indexes,
                "duplicates": self.report.duplicate_indexes,
            },
            "dead_code": {
                "dead_tables": self.report.dead_tables,
                "dead_procedures": self.report.dead_procedures,
                "orphan_columns": self.report.orphan_columns,
                "empty_tables": self.report.empty_tables,
            },
            "sp_analysis": self.report.sp_analysis,
            "dependencies": self.report.dependencies,
            "circular_dependencies": self.report.circular_dependencies,
            "issues": self.report.issues,
            "risk_scores": self.report.risk_scores,
            "security_issues": self.report.security_issues,
            "size_info": self.report.size_info,
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str, ensure_ascii=False)
