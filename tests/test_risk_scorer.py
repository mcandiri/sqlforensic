"""Tests for RiskScorer — per-object migration risk calculation."""

from __future__ import annotations

from sqlforensic import AnalysisReport
from sqlforensic.scoring.risk_scorer import RiskScorer


class TestRiskScorer:
    """Tests for table and SP risk scoring."""

    def test_calculate_returns_tables_and_procedures(self, sample_report: AnalysisReport) -> None:
        """calculate() must return a dict with 'tables' and 'procedures' keys."""
        scorer = RiskScorer(sample_report)
        result = scorer.calculate()

        assert "tables" in result
        assert "procedures" in result
        assert isinstance(result["tables"], list)
        assert isinstance(result["procedures"], list)

    def test_table_risks_sorted_descending(self, sample_report: AnalysisReport) -> None:
        """Table risks should be sorted by risk_score descending."""
        scorer = RiskScorer(sample_report)
        result = scorer.calculate()

        scores = [t["risk_score"] for t in result["tables"]]
        assert scores == sorted(scores, reverse=True)

    def test_sp_risks_sorted_descending(self, sample_report: AnalysisReport) -> None:
        """SP risks should be sorted by risk_score descending."""
        scorer = RiskScorer(sample_report)
        result = scorer.calculate()

        scores = [sp["risk_score"] for sp in result["procedures"]]
        assert scores == sorted(scores, reverse=True)

    def test_table_risk_fields_present(self, sample_report: AnalysisReport) -> None:
        """Each table risk entry should have all required fields."""
        scorer = RiskScorer(sample_report)
        result = scorer.calculate()

        required = {
            "name",
            "schema",
            "risk_score",
            "risk_level",
            "dependent_sp_count",
            "dependent_sps",
            "fk_dependency_count",
            "row_count",
        }
        for entry in result["tables"]:
            assert required.issubset(entry.keys()), (
                f"Table {entry['name']} missing: {required - entry.keys()}"
            )

    def test_sp_risk_fields_present(self, sample_report: AnalysisReport) -> None:
        """Each SP risk entry should have all required fields."""
        scorer = RiskScorer(sample_report)
        result = scorer.calculate()

        required = {
            "name",
            "schema",
            "risk_score",
            "risk_level",
            "complexity_score",
            "referenced_table_count",
            "caller_count",
        }
        for entry in result["procedures"]:
            assert required.issubset(entry.keys()), (
                f"SP {entry['name']} missing: {required - entry.keys()}"
            )

    def test_risk_level_labels_are_valid(self, sample_report: AnalysisReport) -> None:
        """All risk_level values must be one of the defined labels."""
        scorer = RiskScorer(sample_report)
        result = scorer.calculate()

        valid_levels = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "MINIMAL"}
        for entry in result["tables"] + result["procedures"]:
            assert entry["risk_level"] in valid_levels, f"Invalid risk level: {entry['risk_level']}"

    def test_size_risk_thresholds(self) -> None:
        """_size_risk should return correct values for different row counts."""
        assert RiskScorer._size_risk(0) == 0
        assert RiskScorer._size_risk(5_000) == 0
        assert RiskScorer._size_risk(10_000) == 5
        assert RiskScorer._size_risk(100_000) == 10
        assert RiskScorer._size_risk(1_000_000) == 15
        assert RiskScorer._size_risk(10_000_000) == 20
