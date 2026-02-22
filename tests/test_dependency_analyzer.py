"""Tests for DependencyAnalyzer — graph building, cycle detection, hotspots."""

from __future__ import annotations

from sqlforensic.analyzers.dependency_analyzer import DependencyAnalyzer


class TestDependencyAnalyzer:
    """Tests for dependency graph construction and analysis."""

    def _make_analyzer(self, sample_tables: list[dict]) -> DependencyAnalyzer:
        """Helper to build DependencyAnalyzer from conftest mock data."""
        from tests.conftest import (
            MOCK_FOREIGN_KEYS,
            MOCK_STORED_PROCEDURES,
            MOCK_VIEWS,
        )

        return DependencyAnalyzer(
            tables=sample_tables,
            stored_procedures=MOCK_STORED_PROCEDURES,
            foreign_keys=MOCK_FOREIGN_KEYS,
            views=MOCK_VIEWS,
        )

    def test_analyze_returns_expected_keys(self, sample_tables: list[dict]) -> None:
        """analyze() must return graph, circular, criticality, clusters, hotspots."""
        analyzer = self._make_analyzer(sample_tables)
        result = analyzer.analyze()

        expected_keys = {"graph", "circular", "criticality", "clusters", "hotspots"}
        assert expected_keys == set(result.keys())

    def test_graph_contains_nodes_and_edges(self, sample_tables: list[dict]) -> None:
        """The graph dict should have nodes and edges lists."""
        analyzer = self._make_analyzer(sample_tables)
        result = analyzer.analyze()

        graph = result["graph"]
        assert "nodes" in graph
        assert "edges" in graph
        assert len(graph["nodes"]) > 0
        assert len(graph["edges"]) > 0

    def test_table_nodes_present_in_graph(self, sample_tables: list[dict]) -> None:
        """All tables from sample_tables should appear as nodes in the graph."""
        analyzer = self._make_analyzer(sample_tables)
        result = analyzer.analyze()

        node_ids = {n["id"] for n in result["graph"]["nodes"]}
        for table in sample_tables:
            assert table["TABLE_NAME"] in node_ids

    def test_fk_edges_present_in_graph(self, sample_tables: list[dict]) -> None:
        """Foreign key relationships should appear as edges of type 'foreign_key'."""
        analyzer = self._make_analyzer(sample_tables)
        result = analyzer.analyze()

        fk_edges = [e for e in result["graph"]["edges"] if e["type"] == "foreign_key"]
        assert len(fk_edges) >= 5  # We have 5 FKs

        # Check that Enrollments -> Students FK edge exists
        enrollment_student = [
            e for e in fk_edges if e["source"] == "Enrollments" and e["target"] == "Students"
        ]
        assert len(enrollment_student) == 1

    def test_sp_reference_edges_present(self, sample_tables: list[dict]) -> None:
        """SP-to-table references should appear as edges of type 'references'."""
        analyzer = self._make_analyzer(sample_tables)
        result = analyzer.analyze()

        ref_edges = [e for e in result["graph"]["edges"] if e["type"] == "references"]
        assert len(ref_edges) > 0

        # sp_GetStudentGrades references Students
        sp_students = [
            e
            for e in ref_edges
            if e["source"] == "sp_GetStudentGrades" and e["target"] == "Students"
        ]
        assert len(sp_students) == 1

    def test_criticality_sorted_descending(self, sample_tables: list[dict]) -> None:
        """Criticality list should be sorted by score in descending order."""
        analyzer = self._make_analyzer(sample_tables)
        result = analyzer.analyze()

        criticality = result["criticality"]
        scores = [c["score"] for c in criticality]
        assert scores == sorted(scores, reverse=True)

    def test_hotspots_identify_tables_with_sp_dependencies(
        self,
        sample_tables: list[dict],
    ) -> None:
        """Hotspots should list tables that have SPs depending on them."""
        analyzer = self._make_analyzer(sample_tables)
        result = analyzer.analyze()

        hotspots = result["hotspots"]
        # Students is referenced by multiple SPs
        hotspot_tables = {h["table"] for h in hotspots}
        assert "Students" in hotspot_tables

        for hs in hotspots:
            assert "dependent_sp_count" in hs
            assert "risk_level" in hs
            assert hs["dependent_sp_count"] > 0
