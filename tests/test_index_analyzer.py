"""Tests for IndexAnalyzer — missing, unused, and duplicate index detection."""

from __future__ import annotations

from unittest.mock import MagicMock

from sqlforensic.analyzers.index_analyzer import IndexAnalyzer


class TestIndexAnalyzer:
    """Tests for index analysis and recommendations."""

    def test_analyze_returns_all_expected_keys(self, mock_connector: MagicMock) -> None:
        """analyze() returns missing, unused, duplicates, recommendations."""
        analyzer = IndexAnalyzer(mock_connector)
        result = analyzer.analyze()

        expected_keys = {"all", "missing", "unused", "duplicates", "overlapping", "recommendations"}
        assert expected_keys == set(result.keys())

    def test_missing_indexes_detected(self, mock_connector: MagicMock) -> None:
        """Missing indexes from DMV data should be returned with create SQL."""
        analyzer = IndexAnalyzer(mock_connector)
        result = analyzer.analyze()

        missing = result["missing"]
        assert len(missing) == 2

        # Should be sorted by improvement_measure descending
        assert missing[0]["improvement_measure"] >= missing[1]["improvement_measure"]

        # Each missing index should have create_sql
        for idx in missing:
            assert "create_sql" in idx
            assert idx["create_sql"].startswith("CREATE INDEX")

    def test_unused_indexes_detected(self, mock_connector: MagicMock) -> None:
        """Indexes with 0 seeks, scans, and lookups (and not PK/unique) should be unused."""
        analyzer = IndexAnalyzer(mock_connector)
        result = analyzer.analyze()

        unused = result["unused"]
        # IX_Old_Attendance has 0 reads and is not PK/unique
        unused_names = [idx["index_name"] for idx in unused]
        assert "IX_Old_Attendance" in unused_names

        for idx in unused:
            assert "drop_sql" in idx
            assert idx["drop_sql"].startswith("DROP INDEX")

    def test_duplicate_indexes_detected(self, mock_connector: MagicMock) -> None:
        """Indexes covering the same columns on the same table should be flagged as duplicates."""
        analyzer = IndexAnalyzer(mock_connector)
        result = analyzer.analyze()

        duplicates = result["duplicates"]
        # IX_Dup_Enrollments and IX_Enrollments_CourseId both cover "CourseId"
        dup_names = [d["index_name"] for d in duplicates]
        assert "IX_Dup_Enrollments" in dup_names

        for dup in duplicates:
            assert "duplicate_of" in dup
            assert "drop_sql" in dup

    def test_recommendations_generated(self, mock_connector: MagicMock) -> None:
        """Recommendations should include CREATE for missing and DROP for duplicates/unused."""
        analyzer = IndexAnalyzer(mock_connector)
        result = analyzer.analyze()

        recs = result["recommendations"]
        assert len(recs) > 0

        actions = {r["action"] for r in recs}
        assert "CREATE" in actions
        assert "DROP" in actions

    def test_pk_and_unique_indexes_not_flagged_unused(self, mock_connector: MagicMock) -> None:
        """Primary key and unique indexes should never appear in unused list."""
        analyzer = IndexAnalyzer(mock_connector)
        result = analyzer.analyze()

        unused_names = {idx["index_name"] for idx in result["unused"]}
        assert "PK_Students" not in unused_names
        assert "PK_Enrollments" not in unused_names
