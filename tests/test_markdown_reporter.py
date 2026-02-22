"""Tests for MarkdownReporter."""

from __future__ import annotations

import os
import tempfile

import pytest

from sqlforensic import AnalysisReport
from sqlforensic.reporters.markdown_reporter import MarkdownReporter


@pytest.fixture
def full_report(sample_report: AnalysisReport) -> AnalysisReport:
    """Use the shared sample_report from conftest."""
    return sample_report


@pytest.fixture
def empty_report() -> AnalysisReport:
    """Minimal report with no data."""
    return AnalysisReport(database="EmptyDB", provider="sqlserver", health_score=100)


class TestMarkdownReporter:
    def test_export_creates_file(self, full_report: AnalysisReport) -> None:
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            path = f.name
        try:
            MarkdownReporter(full_report).export(path)
            assert os.path.exists(path)
            assert os.path.getsize(path) > 0
        finally:
            os.unlink(path)

    def test_contains_database_name(self, full_report: AnalysisReport) -> None:
        lines = MarkdownReporter(full_report)._build()
        content = "\n".join(lines)
        assert "SchoolDB" in content

    def test_contains_health_score(self, full_report: AnalysisReport) -> None:
        lines = MarkdownReporter(full_report)._build()
        content = "\n".join(lines)
        assert "68" in content

    def test_contains_provider(self, full_report: AnalysisReport) -> None:
        lines = MarkdownReporter(full_report)._build()
        content = "\n".join(lines)
        assert "sqlserver" in content

    def test_schema_section_has_tables(self, full_report: AnalysisReport) -> None:
        lines = MarkdownReporter(full_report)._build()
        content = "\n".join(lines)
        assert "## Schema Overview" in content
        assert "Students" in content

    def test_issues_section_present(self, full_report: AnalysisReport) -> None:
        lines = MarkdownReporter(full_report)._build()
        content = "\n".join(lines)
        assert "## Issues" in content
        assert "HIGH" in content

    def test_relationships_section_has_fks(self, full_report: AnalysisReport) -> None:
        lines = MarkdownReporter(full_report)._build()
        content = "\n".join(lines)
        assert "## Relationships" in content
        assert "Foreign Keys" in content

    def test_implicit_relationships_shown(self, full_report: AnalysisReport) -> None:
        lines = MarkdownReporter(full_report)._build()
        content = "\n".join(lines)
        assert "Implicit Relationships" in content
        assert "naming_convention" in content

    def test_sp_analysis_section(self, full_report: AnalysisReport) -> None:
        lines = MarkdownReporter(full_report)._build()
        content = "\n".join(lines)
        assert "Stored Procedure Analysis" in content
        assert "sp_GetStudentGrades" in content

    def test_index_section_missing_indexes(self, full_report: AnalysisReport) -> None:
        lines = MarkdownReporter(full_report)._build()
        content = "\n".join(lines)
        assert "Missing Indexes" in content

    def test_index_section_unused_indexes(self, full_report: AnalysisReport) -> None:
        lines = MarkdownReporter(full_report)._build()
        content = "\n".join(lines)
        assert "Unused Indexes" in content

    def test_dead_code_section(self, full_report: AnalysisReport) -> None:
        lines = MarkdownReporter(full_report)._build()
        content = "\n".join(lines)
        assert "Dead Code" in content
        assert "Logs_Archive" in content

    def test_dead_procedures_shown(self, full_report: AnalysisReport) -> None:
        lines = MarkdownReporter(full_report)._build()
        content = "\n".join(lines)
        assert "sp_OldReport" in content

    def test_dependency_section_circular(self, full_report: AnalysisReport) -> None:
        lines = MarkdownReporter(full_report)._build()
        content = "\n".join(lines)
        assert "Circular Dependencies" in content
        assert "Schedules" in content

    def test_dependency_hotspots(self, full_report: AnalysisReport) -> None:
        lines = MarkdownReporter(full_report)._build()
        content = "\n".join(lines)
        assert "Dependency Hotspots" in content
        assert "Students" in content

    def test_footer_present(self, full_report: AnalysisReport) -> None:
        lines = MarkdownReporter(full_report)._build()
        content = "\n".join(lines)
        assert "SQLForensic" in content
        assert "---" in content

    def test_empty_report_no_issues_section(self, empty_report: AnalysisReport) -> None:
        lines = MarkdownReporter(empty_report)._build()
        content = "\n".join(lines)
        assert "## Issues" not in content

    def test_empty_report_still_has_schema_section(self, empty_report: AnalysisReport) -> None:
        lines = MarkdownReporter(empty_report)._build()
        content = "\n".join(lines)
        assert "## Schema Overview" in content

    def test_empty_cycle_does_not_crash(self) -> None:
        report = AnalysisReport(
            database="TestDB",
            provider="sqlserver",
            circular_dependencies=[[], ["A", "B"]],
        )
        lines = MarkdownReporter(report)._build()
        content = "\n".join(lines)
        assert "A -> B -> A" in content
