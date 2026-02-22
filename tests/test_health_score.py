"""Tests for HealthScoreCalculator — health score computation."""

from __future__ import annotations

from sqlforensic import AnalysisReport
from sqlforensic.scoring.health_score import HealthScoreCalculator


class TestHealthScoreCalculator:
    """Tests for the health score calculation engine."""

    def test_perfect_score_for_clean_database(self) -> None:
        """A database with no issues should score 100."""
        report = AnalysisReport(
            database="CleanDB",
            tables=[
                {
                    "TABLE_NAME": "Users",
                    "TABLE_SCHEMA": "dbo",
                    "row_count": 100,
                    "columns": [
                        {"COLUMN_NAME": "Id", "is_primary_key": True},
                        {"COLUMN_NAME": "Name", "is_primary_key": False},
                    ],
                    "column_count": 2,
                    "has_primary_key": True,
                },
            ],
            indexes=[{"table_name": "Users", "index_name": "PK_Users"}],
        )
        calc = HealthScoreCalculator(report)
        score = calc.calculate()

        assert score == 100

    def test_score_penalized_for_missing_pk(self) -> None:
        """Tables without PK should reduce the health score by 5 each."""
        report = AnalysisReport(
            database="NoPKDB",
            tables=[
                {
                    "TABLE_NAME": "BadTable",
                    "TABLE_SCHEMA": "dbo",
                    "row_count": 100,
                    "columns": [
                        {"COLUMN_NAME": "Id", "is_primary_key": False},
                    ],
                    "column_count": 1,
                    "has_primary_key": False,
                },
            ],
            indexes=[{"table_name": "BadTable", "index_name": "IX_Something"}],
        )
        calc = HealthScoreCalculator(report)
        score = calc.calculate()

        assert score <= 95  # At least -5 for the missing PK

    def test_score_penalized_for_circular_dependencies(self) -> None:
        """Circular dependencies should cost 10 points each."""
        report = AnalysisReport(
            database="CircularDB",
            circular_dependencies=[["A", "B"], ["C", "D"]],
        )
        calc = HealthScoreCalculator(report)
        score = calc.calculate()

        assert score <= 80  # -20 for two cycles

    def test_sample_report_score_is_reasonable(self, sample_report: AnalysisReport) -> None:
        """The sample report should produce a score between 0 and 100."""
        calc = HealthScoreCalculator(sample_report)
        score = calc.calculate()

        assert 0 <= score <= 100

    def test_get_issues_returns_sorted_list(self, sample_report: AnalysisReport) -> None:
        """Issues should be returned sorted by penalty descending after calculate()."""
        calc = HealthScoreCalculator(sample_report)
        calc.calculate()
        issues = calc.get_issues()

        assert len(issues) > 0
        penalties = [issue["penalty"] for issue in issues]
        assert penalties == sorted(penalties, reverse=True)

    def test_issues_have_required_fields(self, sample_report: AnalysisReport) -> None:
        """Each issue must have description, severity, count, penalty, and category."""
        calc = HealthScoreCalculator(sample_report)
        calc.calculate()
        issues = calc.get_issues()

        required_keys = {"description", "severity", "count", "penalty", "category"}
        for issue in issues:
            assert required_keys.issubset(issue.keys()), (
                f"Issue missing keys: {required_keys - issue.keys()}"
            )
