"""Tests for DeadCodeAnalyzer — dead tables, SPs, orphan columns, empty tables."""

from __future__ import annotations

from sqlforensic.analyzers.dead_code_analyzer import DeadCodeAnalyzer


class TestDeadCodeAnalyzer:
    """Tests for dead code detection logic."""

    def _make_analyzer(self, sample_tables: list[dict]) -> DeadCodeAnalyzer:
        """Helper to build a DeadCodeAnalyzer from conftest mock data."""
        from tests.conftest import (
            MOCK_FOREIGN_KEYS,
            MOCK_STORED_PROCEDURES,
            MOCK_VIEWS,
        )

        return DeadCodeAnalyzer(
            tables=sample_tables,
            stored_procedures=MOCK_STORED_PROCEDURES,
            foreign_keys=MOCK_FOREIGN_KEYS,
            views=MOCK_VIEWS,
        )

    def test_analyze_returns_all_expected_keys(self, sample_tables: list[dict]) -> None:
        """analyze() must return dead_tables, dead_procedures, orphan_columns, empty_tables."""
        analyzer = self._make_analyzer(sample_tables)
        result = analyzer.analyze()

        expected_keys = {"dead_tables", "dead_procedures", "orphan_columns", "empty_tables"}
        assert expected_keys == set(result.keys())

    def test_empty_tables_detected(self, sample_tables: list[dict]) -> None:
        """Tables with row_count == 0 should appear in empty_tables."""
        analyzer = self._make_analyzer(sample_tables)
        result = analyzer.analyze()

        empty_names = {t["TABLE_NAME"] for t in result["empty_tables"]}
        assert "AuditLog" in empty_names
        assert "Logs_Archive" in empty_names
        # Non-empty tables must not appear
        assert "Students" not in empty_names

    def test_dead_tables_not_referenced_anywhere(self, sample_tables: list[dict]) -> None:
        """Tables not in any FK, SP body, or view should be dead."""
        analyzer = self._make_analyzer(sample_tables)
        result = analyzer.analyze()

        dead_names = {t["TABLE_NAME"] for t in result["dead_tables"]}
        # Logs_Archive is not referenced by any FK, SP, or view
        assert "Logs_Archive" in dead_names
        # Students is heavily referenced and must NOT be dead
        assert "Students" not in dead_names

    def test_dead_procedures_not_called_by_others(self, sample_tables: list[dict]) -> None:
        """SPs that are not called/referenced by any other SP should be listed."""
        analyzer = self._make_analyzer(sample_tables)
        result = analyzer.analyze()

        dead_sp_names = {sp["ROUTINE_NAME"] for sp in result["dead_procedures"]}
        # sp_OldReport and sp_TempCleanup are standalone -- not referenced by others
        # Note: the analyzer checks cross-references between SPs
        assert len(dead_sp_names) >= 1

    def test_orphan_columns_detected(self, sample_tables: list[dict]) -> None:
        """Columns not referenced in any SP or view (excluding PKs) should be orphans."""
        analyzer = self._make_analyzer(sample_tables)
        result = analyzer.analyze()

        orphans = result["orphan_columns"]
        # There should be at least some orphan columns
        assert len(orphans) >= 1

        # Primary key columns should never be listed as orphans
        orphan_col_names = {(o["table_name"], o["column_name"]) for o in orphans}
        assert ("Students", "Id") not in orphan_col_names

    def test_referenced_tables_include_fk_tables(self, sample_tables: list[dict]) -> None:
        """Tables involved in foreign keys must not be dead."""
        analyzer = self._make_analyzer(sample_tables)
        result = analyzer.analyze()

        dead_names = {t["TABLE_NAME"] for t in result["dead_tables"]}
        # All these appear in FK relationships
        for table_name in ("Students", "Courses", "Enrollments", "Grades", "Departments"):
            assert table_name not in dead_names
