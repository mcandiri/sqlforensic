"""Tests for ConsoleReporter."""

from __future__ import annotations

from io import StringIO

from rich.console import Console

from sqlforensic import AnalysisReport
from sqlforensic.reporters.console_reporter import ConsoleReporter


def _capture_output(report: AnalysisReport) -> str:
    """Render report to string for assertions."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=120)
    ConsoleReporter(report, console=console).print_report()
    return buf.getvalue()


class TestConsoleReporter:
    def test_prints_database_name(self, sample_report: AnalysisReport) -> None:
        output = _capture_output(sample_report)
        assert "SchoolDB" in output

    def test_prints_health_score(self, sample_report: AnalysisReport) -> None:
        output = _capture_output(sample_report)
        assert "68" in output
        assert "HEALTH SCORE" in output

    def test_prints_schema_overview(self, sample_report: AnalysisReport) -> None:
        output = _capture_output(sample_report)
        assert "Schema Overview" in output

    def test_prints_issues(self, sample_report: AnalysisReport) -> None:
        output = _capture_output(sample_report)
        assert "Issues Found" in output
        assert "HIGH" in output

    def test_prints_hotspots(self, sample_report: AnalysisReport) -> None:
        output = _capture_output(sample_report)
        assert "Hotspots" in output
        assert "Students" in output

    def test_empty_report_no_crash(self) -> None:
        report = AnalysisReport(
            database="EmptyDB",
            provider="sqlserver",
            health_score=100,
        )
        output = _capture_output(report)
        assert "EmptyDB" in output
        assert "100" in output

    def test_no_issues_skips_issues_table(self) -> None:
        report = AnalysisReport(
            database="CleanDB",
            provider="postgresql",
            health_score=95,
        )
        output = _capture_output(report)
        assert "Issues Found" not in output

    def test_no_hotspots_skips_hotspots_table(self) -> None:
        report = AnalysisReport(
            database="CleanDB",
            provider="postgresql",
            health_score=95,
        )
        output = _capture_output(report)
        assert "Hotspots" not in output
