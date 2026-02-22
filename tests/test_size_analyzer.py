"""Tests for SizeAnalyzer."""

from __future__ import annotations

from unittest.mock import MagicMock

from sqlforensic.analyzers.size_analyzer import SizeAnalyzer


class TestSizeAnalyzer:
    def test_returns_sorted_by_size_descending(self, mock_connector: MagicMock) -> None:
        analyzer = SizeAnalyzer(mock_connector)
        results = analyzer.analyze()
        sizes = [r["total_space_kb"] for r in results]
        assert sizes == sorted(sizes, reverse=True)

    def test_all_tables_present(self, mock_connector: MagicMock) -> None:
        analyzer = SizeAnalyzer(mock_connector)
        results = analyzer.analyze()
        names = {r["table_name"] for r in results}
        assert "Grades" in names
        assert "Students" in names

    def test_result_has_required_fields(self, mock_connector: MagicMock) -> None:
        analyzer = SizeAnalyzer(mock_connector)
        results = analyzer.analyze()
        for r in results:
            assert "table_schema" in r
            assert "table_name" in r
            assert "row_count" in r
            assert "total_space_kb" in r
            assert "used_space_kb" in r
            assert "unused_space_kb" in r
            assert "avg_row_size_bytes" in r

    def test_unused_space_calculated(self, mock_connector: MagicMock) -> None:
        analyzer = SizeAnalyzer(mock_connector)
        results = analyzer.analyze()
        for r in results:
            assert r["unused_space_kb"] == r["total_space_kb"] - r["used_space_kb"]

    def test_avg_row_size_positive_for_nonempty(self, mock_connector: MagicMock) -> None:
        analyzer = SizeAnalyzer(mock_connector)
        results = analyzer.analyze()
        for r in results:
            if r["row_count"] > 0:
                assert r["avg_row_size_bytes"] > 0

    def test_avg_row_size_zero_for_empty_table(self) -> None:
        connector = MagicMock()
        connector.get_table_sizes.return_value = [
            {
                "table_schema": "dbo",
                "table_name": "EmptyTable",
                "row_count": 0,
                "total_space_kb": 64,
                "used_space_kb": 8,
            },
        ]
        analyzer = SizeAnalyzer(connector)
        results = analyzer.analyze()
        assert results[0]["avg_row_size_bytes"] == 0

    def test_empty_database_returns_empty(self) -> None:
        connector = MagicMock()
        connector.get_table_sizes.return_value = []
        analyzer = SizeAnalyzer(connector)
        results = analyzer.analyze()
        assert results == []
