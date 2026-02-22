"""Tests for RelationshipAnalyzer — FK and implicit relationship discovery."""

from __future__ import annotations

from unittest.mock import MagicMock

from sqlforensic.analyzers.relationship_analyzer import RelationshipAnalyzer


class TestRelationshipAnalyzer:
    """Tests for explicit and implicit relationship detection."""

    def test_explicit_fk_relationships_returned(
        self,
        mock_connector: MagicMock,
        sample_tables: list[dict],
    ) -> None:
        """analyze() should return all foreign keys from the connector."""
        sps = mock_connector.get_stored_procedures()
        analyzer = RelationshipAnalyzer(mock_connector, sample_tables, sps)
        result = analyzer.analyze()

        explicit = result["explicit"]
        assert len(explicit) == 5

        constraint_names = {fk["constraint_name"] for fk in explicit}
        assert "FK_Enrollments_Students" in constraint_names
        assert "FK_Grades_Courses" in constraint_names

    def test_implicit_relationships_discovered(
        self,
        mock_connector: MagicMock,
        sample_tables: list[dict],
    ) -> None:
        """Implicit relationships should be found from SP JOINs and naming conventions."""
        sps = mock_connector.get_stored_procedures()
        analyzer = RelationshipAnalyzer(mock_connector, sample_tables, sps)
        result = analyzer.analyze()

        implicit = result["implicit"]
        # At minimum, naming convention should pick up Payments.StudentId -> Students
        assert len(implicit) >= 1

    def test_implicit_relationships_have_confidence(
        self,
        mock_connector: MagicMock,
        sample_tables: list[dict],
    ) -> None:
        """Each implicit relationship must have a confidence score and source."""
        sps = mock_connector.get_stored_procedures()
        analyzer = RelationshipAnalyzer(mock_connector, sample_tables, sps)
        result = analyzer.analyze()

        for rel in result["implicit"]:
            assert "confidence" in rel
            assert rel["confidence"] in (60, 80)
            assert "source" in rel
            assert rel["source"] in ("naming_convention", "stored_procedure")

    def test_deduplication_removes_fk_duplicates(
        self,
        mock_connector: MagicMock,
        sample_tables: list[dict],
    ) -> None:
        """Implicit relationships that duplicate explicit FKs should be removed."""
        sps = mock_connector.get_stored_procedures()
        analyzer = RelationshipAnalyzer(mock_connector, sample_tables, sps)
        result = analyzer.analyze()

        explicit_pairs = set()
        for fk in result["explicit"]:
            explicit_pairs.add((fk["parent_table"], fk["referenced_table"]))
            explicit_pairs.add((fk["referenced_table"], fk["parent_table"]))

        for rel in result["implicit"]:
            pair = (rel["parent_table"], rel["referenced_table"])
            assert pair not in explicit_pairs, (
                f"Implicit relationship {pair} duplicates an explicit FK"
            )

    def test_naming_convention_detects_payment_student_link(
        self,
        mock_connector: MagicMock,
        sample_tables: list[dict],
    ) -> None:
        """Payments.StudentId detected as implicit FK to Students."""
        sps = mock_connector.get_stored_procedures()
        analyzer = RelationshipAnalyzer(mock_connector, sample_tables, sps)
        result = analyzer.analyze()

        naming_rels = [r for r in result["implicit"] if r["source"] == "naming_convention"]
        payment_student = [
            r
            for r in naming_rels
            if r["parent_table"] == "Payments" and r["referenced_table"] == "Students"
        ]
        assert len(payment_student) == 1
        assert payment_student[0]["confidence"] == 60
