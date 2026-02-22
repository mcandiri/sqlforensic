"""Tests for SchemaAnalyzer using mock connector fixtures."""

from __future__ import annotations

from unittest.mock import MagicMock

from sqlforensic.analyzers.schema_analyzer import SchemaAnalyzer


class TestSchemaAnalyzer:
    """Tests for the SchemaAnalyzer class."""

    def test_analyze_returns_all_expected_keys(self, mock_connector: MagicMock) -> None:
        """analyze() must return tables, views, SPs, functions, indexes, and overview."""
        analyzer = SchemaAnalyzer(mock_connector)
        result = analyzer.analyze()

        expected_keys = {
            "tables",
            "views",
            "stored_procedures",
            "functions",
            "indexes",
            "foreign_keys",
            "overview",
        }
        assert expected_keys == set(result.keys())

    def test_tables_have_columns_and_pk_flag(self, mock_connector: MagicMock) -> None:
        """Each table dict should contain columns list, column_count, and has_primary_key."""
        analyzer = SchemaAnalyzer(mock_connector)
        result = analyzer.analyze()
        tables = result["tables"]

        assert len(tables) == 8  # MOCK_TABLES has 8 entries

        students = next(t for t in tables if t["TABLE_NAME"] == "Students")
        assert students["column_count"] == 7
        assert students["has_primary_key"] is True
        assert len(students["columns"]) == 7

    def test_tables_without_pk_are_flagged(self, mock_connector: MagicMock) -> None:
        """AuditLog has no PK column (is_primary_key == 0), so has_primary_key should be False."""
        analyzer = SchemaAnalyzer(mock_connector)
        result = analyzer.analyze()
        tables = result["tables"]

        audit = next(t for t in tables if t["TABLE_NAME"] == "AuditLog")
        assert audit["has_primary_key"] is False

    def test_overview_counts_are_correct(self, mock_connector: MagicMock) -> None:
        """The overview dict should have accurate counts for all object types."""
        analyzer = SchemaAnalyzer(mock_connector)
        result = analyzer.analyze()
        overview = result["overview"]

        assert overview["tables"] == 8
        assert overview["views"] == 2
        assert overview["stored_procedures"] == 5
        assert overview["functions"] == 1
        assert overview["indexes"] == 6
        assert overview["foreign_keys"] == 5

    def test_overview_total_rows(self, mock_connector: MagicMock) -> None:
        """Total rows should sum across all tables."""
        analyzer = SchemaAnalyzer(mock_connector)
        result = analyzer.analyze()
        overview = result["overview"]

        # 15000 + 200 + 45000 + 90000 + 32000 + 12 + 0 + 0 = 182212
        assert overview["total_rows"] == 182212

    def test_overview_total_columns(self, mock_connector: MagicMock) -> None:
        """Total columns should sum column_count across all tables."""
        analyzer = SchemaAnalyzer(mock_connector)
        result = analyzer.analyze()
        overview = result["overview"]

        # Students=7, Courses=4, Enrollments=4, Grades=4, Payments=4,
        # Departments=2, AuditLog=2, Logs_Archive=2 = 29
        assert overview["total_columns"] == 29
