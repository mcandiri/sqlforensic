"""Tests for HTMLReporter — HTML report generation."""

from __future__ import annotations

import os
import tempfile

from sqlforensic import AnalysisReport
from sqlforensic.reporters.html_reporter import HTMLReporter


class TestHTMLReporter:
    """Tests for HTML report export functionality."""

    def test_export_creates_file(self, sample_report: AnalysisReport) -> None:
        """export() should create an HTML file at the specified path."""
        reporter = HTMLReporter(sample_report)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "report.html")
            reporter.export(output_path)

            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0

    def test_export_contains_database_name(self, sample_report: AnalysisReport) -> None:
        """The HTML report should contain the database name."""
        reporter = HTMLReporter(sample_report)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "report.html")
            reporter.export(output_path)

            with open(output_path, encoding="utf-8") as f:
                html = f.read()

            assert "SchoolDB" in html

    def test_export_contains_health_score(self, sample_report: AnalysisReport) -> None:
        """The HTML report should contain the health score value."""
        reporter = HTMLReporter(sample_report)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "report.html")
            reporter.export(output_path)

            with open(output_path, encoding="utf-8") as f:
                html = f.read()

            assert str(sample_report.health_score) in html

    def test_export_contains_table_names(self, sample_report: AnalysisReport) -> None:
        """The HTML report should reference key table names."""
        reporter = HTMLReporter(sample_report)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "report.html")
            reporter.export(output_path)

            with open(output_path, encoding="utf-8") as f:
                html = f.read()

            assert "Students" in html
            assert "Enrollments" in html

    def test_export_graph_creates_file(self, sample_report: AnalysisReport) -> None:
        """export_graph() should create an HTML file for the dependency graph."""
        reporter = HTMLReporter(sample_report)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "graph.html")
            reporter.export_graph(output_path)

            assert os.path.exists(output_path)
            assert os.path.getsize(output_path) > 0

    def test_build_graph_json_valid(self, sample_report: AnalysisReport) -> None:
        """_build_graph_json should return valid JSON with nodes and links."""
        import json

        reporter = HTMLReporter(sample_report)
        graph_json = reporter._build_graph_json()

        data = json.loads(graph_json)
        assert "nodes" in data
        assert "links" in data
        assert isinstance(data["nodes"], list)
        assert isinstance(data["links"], list)
