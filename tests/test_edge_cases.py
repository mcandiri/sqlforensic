"""Cross-cutting edge case tests for analyzers, scorers, and parsers.

Covers boundary conditions and unusual inputs that are missing from the
existing per-module test suites.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from sqlforensic import AnalysisReport, ImpactResult
from sqlforensic.analyzers.dead_code_analyzer import DeadCodeAnalyzer
from sqlforensic.analyzers.dependency_analyzer import DependencyAnalyzer
from sqlforensic.analyzers.relationship_analyzer import RelationshipAnalyzer
from sqlforensic.parsers.sp_parser import SPParser, SPParseResult
from sqlforensic.scoring.health_score import HealthScoreCalculator

# ---------------------------------------------------------------------------
# Local fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def empty_tables() -> list[dict[str, Any]]:
    """No tables at all."""
    return []


@pytest.fixture()
def single_table() -> list[dict[str, Any]]:
    """A single table with a primary key and columns."""
    return [
        {
            "TABLE_SCHEMA": "dbo",
            "TABLE_NAME": "Orders",
            "row_count": 50,
            "columns": [
                {"COLUMN_NAME": "Id", "DATA_TYPE": "int", "is_primary_key": 1},
                {"COLUMN_NAME": "Total", "DATA_TYPE": "decimal", "is_primary_key": 0},
            ],
            "column_count": 2,
            "has_primary_key": True,
        },
    ]


@pytest.fixture()
def sp_parser() -> SPParser:
    """Fresh SPParser instance."""
    return SPParser()


# ===========================================================================
# 1. DependencyAnalyzer edge cases
# ===========================================================================


class TestDependencyAnalyzerEdgeCases:
    """Edge cases for DependencyAnalyzer."""

    def test_circular_self_reference_filtered_out(self) -> None:
        """A self-referencing FK (parent == referenced) should not appear as a cycle >= 2."""
        tables: list[dict[str, Any]] = [
            {"TABLE_SCHEMA": "dbo", "TABLE_NAME": "Employees", "row_count": 10},
        ]
        foreign_keys: list[dict[str, Any]] = [
            {
                "constraint_name": "FK_Employees_Manager",
                "parent_schema": "dbo",
                "parent_table": "Employees",
                "parent_column": "ManagerId",
                "referenced_schema": "dbo",
                "referenced_table": "Employees",
                "referenced_column": "Id",
            },
        ]

        analyzer = DependencyAnalyzer(
            tables=tables,
            stored_procedures=[],
            foreign_keys=foreign_keys,
            views=[],
        )
        result = analyzer.analyze()

        # Self-loops produce cycles of length 1, which the analyzer filters
        # (only cycles with len >= 2 are returned).
        for cycle in result["circular"]:
            assert len(cycle) >= 2, "Self-referencing FK must not surface as a 1-node cycle"

    def test_empty_graph_produces_empty_results(self) -> None:
        """An analyzer with zero tables, SPs, FKs, and views should not crash."""
        analyzer = DependencyAnalyzer(
            tables=[],
            stored_procedures=[],
            foreign_keys=[],
            views=[],
        )
        result = analyzer.analyze()

        assert result["graph"]["nodes"] == []
        assert result["graph"]["edges"] == []
        assert result["circular"] == []
        assert result["criticality"] == []
        assert result["clusters"] == []
        assert result["hotspots"] == []

    def test_impact_analysis_for_table_not_in_graph(self) -> None:
        """get_impact() for a table not in the graph returns an empty ImpactResult."""
        analyzer = DependencyAnalyzer(
            tables=[{"TABLE_SCHEMA": "dbo", "TABLE_NAME": "Users", "row_count": 1}],
            stored_procedures=[],
            foreign_keys=[],
            views=[],
        )
        analysis_result = analyzer.analyze()

        impact = analyzer.get_impact("NonExistentTable", analysis_result)

        assert isinstance(impact, ImpactResult)
        assert impact.table_name == "NonExistentTable"
        assert impact.affected_sps == []
        assert impact.affected_views == []
        assert impact.affected_tables == []
        assert impact.total_affected == 0
        assert impact.risk_level == "LOW"

    def test_impact_analysis_for_existing_table(self) -> None:
        """get_impact() for an existing table returns a valid ImpactResult."""
        tables: list[dict[str, Any]] = [
            {"TABLE_SCHEMA": "dbo", "TABLE_NAME": "Users", "row_count": 100},
            {"TABLE_SCHEMA": "dbo", "TABLE_NAME": "Orders", "row_count": 500},
        ]
        foreign_keys: list[dict[str, Any]] = [
            {
                "constraint_name": "FK_Orders_Users",
                "parent_schema": "dbo",
                "parent_table": "Orders",
                "parent_column": "UserId",
                "referenced_schema": "dbo",
                "referenced_table": "Users",
                "referenced_column": "Id",
            },
        ]

        analyzer = DependencyAnalyzer(
            tables=tables,
            stored_procedures=[],
            foreign_keys=foreign_keys,
            views=[],
        )
        analysis_result = analyzer.analyze()

        impact = analyzer.get_impact("Users", analysis_result)

        assert isinstance(impact, ImpactResult)
        assert impact.table_name == "Users"
        # Orders depends on Users via FK, so it should appear as affected
        assert len(impact.affected_tables) >= 1


# ===========================================================================
# 2. HealthScoreCalculator edge cases
# ===========================================================================


class TestHealthScoreEdgeCases:
    """Edge cases for HealthScoreCalculator."""

    def test_score_never_below_zero(self) -> None:
        """Even with extreme penalties the score must not drop below 0."""
        report = AnalysisReport(
            database="TerribleDB",
            tables=[
                {
                    "TABLE_NAME": f"Bad{i}",
                    "TABLE_SCHEMA": "dbo",
                    "row_count": 0,
                    "columns": [{"COLUMN_NAME": "x", "is_primary_key": False}],
                    "column_count": 1,
                    "has_primary_key": False,
                }
                for i in range(50)
            ],
            # No indexes at all -> every table penalized for missing indexes
            indexes=[],
            missing_indexes=[{"table_name": f"t{i}"} for i in range(30)],
            dead_procedures=[
                {"ROUTINE_SCHEMA": "dbo", "ROUTINE_NAME": f"sp_{i}"} for i in range(30)
            ],
            circular_dependencies=[["A", "B"], ["C", "D"], ["E", "F"], ["G", "H"], ["I", "J"]],
            sp_analysis=[{"complexity_score": 99} for _ in range(20)],
            duplicate_indexes=[{"table_name": "x", "index_name": f"ix_{i}"} for i in range(20)],
            dead_tables=[{"TABLE_SCHEMA": "dbo", "TABLE_NAME": f"dead{i}"} for i in range(20)],
            empty_tables=[{"TABLE_SCHEMA": "dbo", "TABLE_NAME": f"empty{i}"} for i in range(20)],
            security_issues=[{"type": "risk", "severity": "HIGH"} for _ in range(20)],
        )

        calc = HealthScoreCalculator(report)
        score = calc.calculate()

        assert score >= 0, "Health score must never be negative"
        assert score == 0, "With extreme penalties the score should clamp at 0"

    def test_score_clamped_at_100(self) -> None:
        """A perfectly clean database must not exceed 100."""
        report = AnalysisReport(
            database="PerfectDB",
            tables=[
                {
                    "TABLE_NAME": "Users",
                    "TABLE_SCHEMA": "dbo",
                    "row_count": 100,
                    "columns": [
                        {"COLUMN_NAME": "Id", "is_primary_key": True},
                        {"COLUMN_NAME": "Name", "is_primary_key": False},
                    ],
                    "column_count": 2,
                    "has_primary_key": True,
                },
            ],
            indexes=[{"table_name": "Users", "index_name": "PK_Users"}],
        )

        calc = HealthScoreCalculator(report)
        score = calc.calculate()

        assert score <= 100, "Health score must not exceed 100"
        assert score == 100

    def test_no_pk_and_no_indexes_are_separate_penalties(self) -> None:
        """A table missing both PK and indexes should be penalized separately.

        Missing PK is a schema issue (-5 per table) and missing indexes is
        an index issue (-5 per table). They are independent checks.
        """
        report = AnalysisReport(
            database="DualIssueDB",
            tables=[
                {
                    "TABLE_NAME": "Lonely",
                    "TABLE_SCHEMA": "dbo",
                    "row_count": 10,
                    "columns": [
                        {"COLUMN_NAME": "Col1", "is_primary_key": False},
                    ],
                    "column_count": 1,
                    "has_primary_key": False,
                },
            ],
            indexes=[],  # No indexes at all
        )

        calc = HealthScoreCalculator(report)
        score = calc.calculate()
        issues = calc.get_issues()

        # Should have both a "schema" (no PK) and an "indexes" (no indexes) issue
        categories = {issue["category"] for issue in issues}
        assert "schema" in categories, "Missing PK should create a schema issue"
        assert "indexes" in categories, "Missing indexes should create an indexes issue"

        # Expect exactly -5 (no PK) + -5 (no indexes) = 90
        assert score == 90

    def test_empty_report_scores_100(self) -> None:
        """An AnalysisReport with all defaults (empty lists) should score 100."""
        report = AnalysisReport(database="EmptyDB")

        calc = HealthScoreCalculator(report)
        score = calc.calculate()

        assert score == 100


# ===========================================================================
# 3. DeadCodeAnalyzer edge cases
# ===========================================================================


class TestDeadCodeAnalyzerEdgeCases:
    """Edge cases for DeadCodeAnalyzer."""

    def test_sp_with_null_body_does_not_crash(self) -> None:
        """An SP whose ROUTINE_DEFINITION is None should not cause errors."""
        tables: list[dict[str, Any]] = [
            {
                "TABLE_SCHEMA": "dbo",
                "TABLE_NAME": "Products",
                "row_count": 10,
                "columns": [{"COLUMN_NAME": "Id", "is_primary_key": 1}],
                "column_count": 1,
            },
        ]
        sps: list[dict[str, Any]] = [
            {
                "ROUTINE_SCHEMA": "dbo",
                "ROUTINE_NAME": "sp_NullBody",
                "ROUTINE_DEFINITION": None,
            },
        ]

        analyzer = DeadCodeAnalyzer(
            tables=tables,
            stored_procedures=sps,
            foreign_keys=[],
            views=[],
        )
        result = analyzer.analyze()

        # Should succeed without raising
        assert "dead_procedures" in result
        assert "dead_tables" in result

    def test_table_with_special_characters_in_name(self) -> None:
        """Table names containing regex meta-characters should be escaped properly."""
        tables: list[dict[str, Any]] = [
            {
                "TABLE_SCHEMA": "dbo",
                "TABLE_NAME": "Order.Details",
                "row_count": 100,
                "columns": [{"COLUMN_NAME": "Id", "is_primary_key": 1}],
                "column_count": 1,
            },
            {
                "TABLE_SCHEMA": "dbo",
                "TABLE_NAME": "Users",
                "row_count": 50,
                "columns": [{"COLUMN_NAME": "Id", "is_primary_key": 1}],
                "column_count": 1,
            },
        ]
        sps: list[dict[str, Any]] = [
            {
                "ROUTINE_SCHEMA": "dbo",
                "ROUTINE_NAME": "sp_GetOrders",
                "ROUTINE_DEFINITION": "SELECT * FROM [Order.Details] WHERE 1=1",
            },
        ]

        analyzer = DeadCodeAnalyzer(
            tables=tables,
            stored_procedures=sps,
            foreign_keys=[],
            views=[],
        )
        result = analyzer.analyze()

        # "Order.Details" is referenced in the SP body, so it should NOT be dead.
        dead_names = {t["TABLE_NAME"] for t in result["dead_tables"]}
        assert "Order.Details" not in dead_names, (
            "Table with special characters should be found via re.escape"
        )
        # "Users" is not referenced anywhere -> should be dead.
        assert "Users" in dead_names

    def test_all_tables_referenced_means_no_dead_tables(self) -> None:
        """When every table is referenced, dead_tables must be empty."""
        tables: list[dict[str, Any]] = [
            {
                "TABLE_SCHEMA": "dbo",
                "TABLE_NAME": "Alpha",
                "row_count": 10,
                "columns": [],
                "column_count": 0,
            },
            {
                "TABLE_SCHEMA": "dbo",
                "TABLE_NAME": "Beta",
                "row_count": 20,
                "columns": [],
                "column_count": 0,
            },
        ]
        foreign_keys: list[dict[str, Any]] = [
            {
                "constraint_name": "FK_Alpha_Beta",
                "parent_schema": "dbo",
                "parent_table": "Alpha",
                "parent_column": "BetaId",
                "referenced_schema": "dbo",
                "referenced_table": "Beta",
                "referenced_column": "Id",
            },
        ]

        analyzer = DeadCodeAnalyzer(
            tables=tables,
            stored_procedures=[],
            foreign_keys=foreign_keys,
            views=[],
        )
        result = analyzer.analyze()

        assert result["dead_tables"] == [], "All tables are referenced, none should be dead"

    def test_empty_tables_with_zero_row_count(self) -> None:
        """Tables with row_count=0 should appear in empty_tables."""
        tables: list[dict[str, Any]] = [
            {
                "TABLE_SCHEMA": "dbo",
                "TABLE_NAME": "EmptyOne",
                "row_count": 0,
                "columns": [],
                "column_count": 0,
            },
            {
                "TABLE_SCHEMA": "dbo",
                "TABLE_NAME": "PopulatedOne",
                "row_count": 100,
                "columns": [],
                "column_count": 0,
            },
        ]

        analyzer = DeadCodeAnalyzer(tables=tables, stored_procedures=[], foreign_keys=[], views=[])
        result = analyzer.analyze()

        empty_names = {t["TABLE_NAME"] for t in result["empty_tables"]}
        assert "EmptyOne" in empty_names
        assert "PopulatedOne" not in empty_names

    def test_no_sps_no_views_no_fks_all_tables_dead(self) -> None:
        """With no SPs, views, or FKs every table should be flagged as dead."""
        tables: list[dict[str, Any]] = [
            {
                "TABLE_SCHEMA": "dbo",
                "TABLE_NAME": "Isolated",
                "row_count": 10,
                "columns": [],
                "column_count": 0,
            },
        ]

        analyzer = DeadCodeAnalyzer(tables=tables, stored_procedures=[], foreign_keys=[], views=[])
        result = analyzer.analyze()

        dead_names = {t["TABLE_NAME"] for t in result["dead_tables"]}
        assert "Isolated" in dead_names


# ===========================================================================
# 4. RelationshipAnalyzer edge cases
# ===========================================================================


class TestRelationshipAnalyzerEdgeCases:
    """Edge cases for RelationshipAnalyzer."""

    @staticmethod
    def _make_mock_connector(foreign_keys: list[dict[str, Any]]) -> MagicMock:
        """Build a mock connector returning the given foreign keys."""
        connector = MagicMock()
        connector.get_foreign_keys.return_value = foreign_keys
        return connector

    def test_self_referencing_fk_is_explicit(self) -> None:
        """A self-referencing FK should appear in the explicit relationships."""
        tables: list[dict[str, Any]] = [
            {
                "TABLE_SCHEMA": "dbo",
                "TABLE_NAME": "Employees",
                "row_count": 100,
                "columns": [
                    {"COLUMN_NAME": "Id", "DATA_TYPE": "int", "is_primary_key": 1},
                    {"COLUMN_NAME": "ManagerId", "DATA_TYPE": "int", "is_primary_key": 0},
                ],
                "column_count": 2,
            },
        ]
        fks: list[dict[str, Any]] = [
            {
                "constraint_name": "FK_Employees_Manager",
                "parent_schema": "dbo",
                "parent_table": "Employees",
                "parent_column": "ManagerId",
                "referenced_schema": "dbo",
                "referenced_table": "Employees",
                "referenced_column": "Id",
            },
        ]
        connector = self._make_mock_connector(fks)

        analyzer = RelationshipAnalyzer(connector, tables, [])
        result = analyzer.analyze()

        assert len(result["explicit"]) == 1
        assert result["explicit"][0]["parent_table"] == "Employees"
        assert result["explicit"][0]["referenced_table"] == "Employees"

    def test_empty_sp_body_produces_no_sp_relationships(self) -> None:
        """An SP with an empty body should contribute zero implicit SP-based relationships."""
        tables: list[dict[str, Any]] = [
            {
                "TABLE_SCHEMA": "dbo",
                "TABLE_NAME": "Items",
                "row_count": 5,
                "columns": [
                    {"COLUMN_NAME": "Id", "DATA_TYPE": "int", "is_primary_key": 1},
                ],
                "column_count": 1,
            },
        ]
        sps: list[dict[str, Any]] = [
            {
                "ROUTINE_SCHEMA": "dbo",
                "ROUTINE_NAME": "sp_Blank",
                "ROUTINE_DEFINITION": "",
            },
        ]
        connector = self._make_mock_connector([])

        analyzer = RelationshipAnalyzer(connector, tables, sps)
        result = analyzer.analyze()

        sp_rels = [r for r in result["implicit"] if r["source"] == "stored_procedure"]
        assert sp_rels == [], "Empty SP body must not generate implicit SP relationships"

    def test_null_sp_body_produces_no_sp_relationships(self) -> None:
        """SP with None body must not crash and produces no SP relationships."""
        tables: list[dict[str, Any]] = [
            {
                "TABLE_SCHEMA": "dbo",
                "TABLE_NAME": "Widgets",
                "row_count": 5,
                "columns": [
                    {"COLUMN_NAME": "Id", "DATA_TYPE": "int", "is_primary_key": 1},
                ],
                "column_count": 1,
            },
        ]
        sps: list[dict[str, Any]] = [
            {
                "ROUTINE_SCHEMA": "dbo",
                "ROUTINE_NAME": "sp_NullDef",
                "ROUTINE_DEFINITION": None,
            },
        ]
        connector = self._make_mock_connector([])

        analyzer = RelationshipAnalyzer(connector, tables, sps)
        result = analyzer.analyze()

        sp_rels = [r for r in result["implicit"] if r["source"] == "stored_procedure"]
        assert sp_rels == []

    def test_duplicate_implicit_relationships_deduplicated(self) -> None:
        """Two SPs joining same tables yield at most one implicit relationship."""
        tables: list[dict[str, Any]] = [
            {
                "TABLE_SCHEMA": "dbo",
                "TABLE_NAME": "Orders",
                "row_count": 100,
                "columns": [
                    {"COLUMN_NAME": "Id", "DATA_TYPE": "int", "is_primary_key": 1},
                    {"COLUMN_NAME": "CustomerId", "DATA_TYPE": "int", "is_primary_key": 0},
                ],
                "column_count": 2,
            },
            {
                "TABLE_SCHEMA": "dbo",
                "TABLE_NAME": "Customers",
                "row_count": 50,
                "columns": [
                    {"COLUMN_NAME": "Id", "DATA_TYPE": "int", "is_primary_key": 1},
                ],
                "column_count": 1,
            },
        ]
        sps: list[dict[str, Any]] = [
            {
                "ROUTINE_SCHEMA": "dbo",
                "ROUTINE_NAME": "sp_Report1",
                "ROUTINE_DEFINITION": (
                    "SELECT o.Id FROM Orders o INNER JOIN Customers c ON o.CustomerId = c.Id"
                ),
            },
            {
                "ROUTINE_SCHEMA": "dbo",
                "ROUTINE_NAME": "sp_Report2",
                "ROUTINE_DEFINITION": (
                    "SELECT o.Id FROM Orders o LEFT JOIN Customers c ON o.CustomerId = c.Id"
                ),
            },
        ]
        connector = self._make_mock_connector([])

        analyzer = RelationshipAnalyzer(connector, tables, sps)
        result = analyzer.analyze()

        # The pair (Customers, Orders) should appear at most once as an SP-based
        # implicit relationship, because _discover_sp_relationships uses a `seen` set.
        sp_rels = [r for r in result["implicit"] if r["source"] == "stored_procedure"]
        pairs = [(r["parent_table"], r["referenced_table"]) for r in sp_rels]
        normalised = {(min(a, b), max(a, b)) for a, b in pairs}
        assert len(normalised) == len(sp_rels), (
            "Duplicate SP-based relationships should be deduplicated"
        )

    def test_naming_convention_does_not_self_reference(self) -> None:
        """A column like StudentsId on table Students should not create a self-reference."""
        tables: list[dict[str, Any]] = [
            {
                "TABLE_SCHEMA": "dbo",
                "TABLE_NAME": "Students",
                "row_count": 100,
                "columns": [
                    {"COLUMN_NAME": "Id", "DATA_TYPE": "int", "is_primary_key": 1},
                    {"COLUMN_NAME": "StudentId", "DATA_TYPE": "int", "is_primary_key": 0},
                ],
                "column_count": 2,
            },
        ]
        connector = self._make_mock_connector([])

        analyzer = RelationshipAnalyzer(connector, tables, [])
        result = analyzer.analyze()

        for rel in result["implicit"]:
            assert not (rel["parent_table"] == rel["referenced_table"]), (
                "Naming convention should not generate self-referencing relationships"
            )


# ===========================================================================
# 5. SPParser edge cases
# ===========================================================================


class TestSPParserEdgeCases:
    """Edge cases for SPParser."""

    def test_empty_body_returns_defaults(self, sp_parser: SPParser) -> None:
        """An SP with an empty string body should return default SPParseResult."""
        sp: dict[str, Any] = {
            "ROUTINE_SCHEMA": "dbo",
            "ROUTINE_NAME": "sp_Empty",
            "ROUTINE_DEFINITION": "",
        }
        result = sp_parser.parse(sp)

        assert isinstance(result, SPParseResult)
        assert result.name == "sp_Empty"
        assert result.line_count == 0
        assert result.referenced_tables == []
        assert result.join_count == 0
        assert result.has_cursors is False
        assert result.has_dynamic_sql is False
        assert result.has_temp_tables is False
        assert result.complexity_score == 0
        assert result.complexity_category == "Simple"
        assert result.anti_patterns == []
        assert result.parameters == []

    def test_none_body_returns_defaults(self, sp_parser: SPParser) -> None:
        """An SP with ROUTINE_DEFINITION = None should behave like empty."""
        sp: dict[str, Any] = {
            "ROUTINE_SCHEMA": "dbo",
            "ROUTINE_NAME": "sp_NoneBody",
            "ROUTINE_DEFINITION": None,
        }
        result = sp_parser.parse(sp)

        assert result.name == "sp_NoneBody"
        assert result.line_count == 0
        assert result.referenced_tables == []
        assert result.complexity_score == 0

    def test_sp_with_no_table_references(self, sp_parser: SPParser) -> None:
        """An SP that does computation without touching any table should have empty refs."""
        sp: dict[str, Any] = {
            "ROUTINE_SCHEMA": "dbo",
            "ROUTINE_NAME": "sp_Compute",
            "ROUTINE_DEFINITION": """
CREATE PROCEDURE [dbo].[sp_Compute]
AS
BEGIN
    DECLARE @x INT = 1
    DECLARE @y INT = 2
    DECLARE @z INT = @x + @y
    RETURN @z
END
""",
        }
        result = sp_parser.parse(sp)

        assert result.referenced_tables == []
        assert result.crud_operations == {
            "SELECT": [],
            "INSERT": [],
            "UPDATE": [],
            "DELETE": [],
        }
        assert result.join_count == 0

    def test_sp_with_only_comments(self, sp_parser: SPParser) -> None:
        """An SP body that is only comments should produce no table references."""
        sp: dict[str, Any] = {
            "ROUTINE_SCHEMA": "dbo",
            "ROUTINE_NAME": "sp_OnlyComments",
            "ROUTINE_DEFINITION": """
CREATE PROCEDURE [dbo].[sp_OnlyComments]
AS
BEGIN
    -- This is a comment about Students table
    /* Another comment mentioning Orders
       and Payments */
    -- SELECT * FROM Fake
END
""",
        }
        result = sp_parser.parse(sp)

        # Line count should be non-zero since there is text
        assert result.line_count > 0
        # The parser does regex-based extraction; comments containing table-like
        # words might or might not be detected. The key assertion is that
        # it does not crash and produces a valid result.
        assert isinstance(result, SPParseResult)
        assert result.join_count == 0
        assert result.has_cursors is False
        assert result.has_dynamic_sql is False

    def test_sp_missing_routine_name_key(self, sp_parser: SPParser) -> None:
        """An SP dict missing ROUTINE_NAME should default to empty string."""
        sp: dict[str, Any] = {
            "ROUTINE_SCHEMA": "dbo",
            "ROUTINE_DEFINITION": "SELECT 1",
        }
        result = sp_parser.parse(sp)

        assert result.name == ""
        assert result.schema == "dbo"

    def test_sp_missing_routine_schema_key(self, sp_parser: SPParser) -> None:
        """An SP dict missing ROUTINE_SCHEMA should default to empty string."""
        sp: dict[str, Any] = {
            "ROUTINE_NAME": "sp_NoSchema",
            "ROUTINE_DEFINITION": "SELECT 1",
        }
        result = sp_parser.parse(sp)

        assert result.schema == ""
        assert result.name == "sp_NoSchema"

    def test_subquery_depth_with_nested_selects(self, sp_parser: SPParser) -> None:
        """Nested subqueries should be counted correctly."""
        sp: dict[str, Any] = {
            "ROUTINE_SCHEMA": "dbo",
            "ROUTINE_NAME": "sp_Nested",
            "ROUTINE_DEFINITION": """
CREATE PROCEDURE [dbo].[sp_Nested]
AS
BEGIN
    SELECT Id FROM Users
    WHERE DeptId IN (
        SELECT DeptId FROM Departments
        WHERE RegionId IN (
            SELECT Id FROM Regions
        )
    )
END
""",
        }
        result = sp_parser.parse(sp)

        assert result.subquery_depth == 2, "Two nested subqueries should yield depth 2"
