"""Tests for JSONReporter."""

from __future__ import annotations

import json
import os
import tempfile

from sqlforensic import AnalysisReport, __version__
from sqlforensic.reporters.json_reporter import JSONReporter


class TestJSONReporter:
    def test_export_creates_valid_json(self, sample_report: AnalysisReport) -> None:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            JSONReporter(sample_report).export(path)
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            assert isinstance(data, dict)
        finally:
            os.unlink(path)

    def test_metadata_contains_version(self, sample_report: AnalysisReport) -> None:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            JSONReporter(sample_report).export(path)
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            assert data["metadata"]["version"] == __version__
            assert data["metadata"]["tool"] == "SQLForensic"
        finally:
            os.unlink(path)

    def test_contains_database_name(self, sample_report: AnalysisReport) -> None:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            JSONReporter(sample_report).export(path)
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            assert data["metadata"]["database"] == "SchoolDB"
        finally:
            os.unlink(path)

    def test_health_score_present(self, sample_report: AnalysisReport) -> None:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            JSONReporter(sample_report).export(path)
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            assert data["health_score"] == 68
        finally:
            os.unlink(path)

    def test_all_top_level_keys_present(self, sample_report: AnalysisReport) -> None:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            JSONReporter(sample_report).export(path)
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            expected_keys = {
                "metadata",
                "health_score",
                "schema_overview",
                "tables",
                "views",
                "stored_procedures",
                "relationships",
                "indexes",
                "dead_code",
                "sp_analysis",
                "dependencies",
                "circular_dependencies",
                "issues",
                "risk_scores",
                "security_issues",
                "size_info",
            }
            assert expected_keys.issubset(set(data.keys()))
        finally:
            os.unlink(path)

    def test_sp_definitions_excluded(self, sample_report: AnalysisReport) -> None:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            JSONReporter(sample_report).export(path)
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            for sp in data["stored_procedures"]:
                assert "ROUTINE_DEFINITION" not in sp
        finally:
            os.unlink(path)

    def test_relationships_split_explicit_implicit(self, sample_report: AnalysisReport) -> None:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            JSONReporter(sample_report).export(path)
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            assert "explicit" in data["relationships"]
            assert "implicit" in data["relationships"]
        finally:
            os.unlink(path)
