"""Tests for sp_differ.py — stored procedure, view, and function diff logic."""

from __future__ import annotations

from sqlforensic.diff.diff_result import hash_body
from sqlforensic.diff.sp_differ import diff_functions, diff_procedures, diff_views

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSPDiffer:
    """Tests for diff_procedures, diff_views, diff_functions."""

    def test_identical_procedures(self) -> None:
        """Identical stored procedures should produce an empty ObjectDiff."""
        sps = [
            {
                "ROUTINE_SCHEMA": "dbo",
                "ROUTINE_NAME": "sp_GetData",
                "ROUTINE_DEFINITION": "CREATE PROCEDURE sp_GetData AS SELECT 1",
            },
        ]

        result = diff_procedures(sps, sps)

        assert result.added == []
        assert result.removed == []
        assert result.modified == []

    def test_added_procedure(self) -> None:
        """A procedure that only exists in source should appear in the added list."""
        source = [
            {
                "ROUTINE_SCHEMA": "dbo",
                "ROUTINE_NAME": "sp_New",
                "ROUTINE_DEFINITION": "CREATE PROCEDURE sp_New AS SELECT 1",
            },
        ]
        target: list[dict] = []

        result = diff_procedures(source, target)

        assert len(result.added) == 1
        assert result.added[0]["name"] == "sp_New"
        assert result.removed == []
        assert result.modified == []

    def test_removed_procedure(self) -> None:
        """A procedure that only exists in target should appear in the removed list."""
        source: list[dict] = []
        target = [
            {
                "ROUTINE_SCHEMA": "dbo",
                "ROUTINE_NAME": "sp_Legacy",
                "ROUTINE_DEFINITION": "CREATE PROCEDURE sp_Legacy AS SELECT 1",
            },
        ]

        result = diff_procedures(source, target)

        assert result.added == []
        assert len(result.removed) == 1
        assert result.removed[0]["name"] == "sp_Legacy"
        assert result.modified == []

    def test_modified_procedure(self) -> None:
        """Same SP name with different body should appear in modified list with different hashes."""
        source = [
            {
                "ROUTINE_SCHEMA": "dbo",
                "ROUTINE_NAME": "sp_Report",
                "ROUTINE_DEFINITION": "CREATE PROCEDURE sp_Report AS SELECT Id, Name FROM Users",
            },
        ]
        target = [
            {
                "ROUTINE_SCHEMA": "dbo",
                "ROUTINE_NAME": "sp_Report",
                "ROUTINE_DEFINITION": "CREATE PROCEDURE sp_Report AS SELECT * FROM Users",
            },
        ]

        result = diff_procedures(source, target)

        assert result.added == []
        assert result.removed == []
        assert len(result.modified) == 1
        mod = result.modified[0]
        assert mod.name == "sp_Report"
        assert mod.object_type == "procedure"
        assert mod.source_hash != mod.target_hash

    def test_view_diff(self) -> None:
        """diff_views should detect added, removed, and modified views."""
        source = [
            {
                "TABLE_SCHEMA": "dbo",
                "TABLE_NAME": "vw_Active",
                "VIEW_DEFINITION": "SELECT * FROM Users WHERE Active = 1",
            },
            {
                "TABLE_SCHEMA": "dbo",
                "TABLE_NAME": "vw_New",
                "VIEW_DEFINITION": "SELECT * FROM Orders",
            },
        ]
        target = [
            {
                "TABLE_SCHEMA": "dbo",
                "TABLE_NAME": "vw_Active",
                "VIEW_DEFINITION": "SELECT * FROM Users WHERE Active = 1 AND Deleted = 0",
            },
            {
                "TABLE_SCHEMA": "dbo",
                "TABLE_NAME": "vw_Old",
                "VIEW_DEFINITION": "SELECT * FROM Archive",
            },
        ]

        result = diff_views(source, target)

        added_names = [v["name"] for v in result.added]
        removed_names = [v["name"] for v in result.removed]
        modified_names = [m.name for m in result.modified]

        assert "vw_New" in added_names
        assert "vw_Old" in removed_names
        assert "vw_Active" in modified_names

    def test_function_diff(self) -> None:
        """diff_functions should detect added, removed, and modified functions."""
        source = [
            {
                "ROUTINE_SCHEMA": "dbo",
                "ROUTINE_NAME": "fn_CalcTotal",
                "ROUTINE_DEFINITION": (
                    "CREATE FUNCTION fn_CalcTotal() RETURNS INT AS BEGIN RETURN 42 END"
                ),
            },
        ]
        target = [
            {
                "ROUTINE_SCHEMA": "dbo",
                "ROUTINE_NAME": "fn_CalcTotal",
                "ROUTINE_DEFINITION": (
                    "CREATE FUNCTION fn_CalcTotal() RETURNS INT AS BEGIN RETURN 99 END"
                ),
            },
            {
                "ROUTINE_SCHEMA": "dbo",
                "ROUTINE_NAME": "fn_OldFunc",
                "ROUTINE_DEFINITION": (
                    "CREATE FUNCTION fn_OldFunc() RETURNS INT AS BEGIN RETURN 0 END"
                ),
            },
        ]

        result = diff_functions(source, target)

        assert result.added == []
        assert len(result.removed) == 1
        assert result.removed[0]["name"] == "fn_OldFunc"
        assert len(result.modified) == 1
        assert result.modified[0].name == "fn_CalcTotal"

    def test_hash_body_normalization(self) -> None:
        """Whitespace-only differences should NOT count as changes."""
        body_a = "  CREATE PROCEDURE sp_Test  AS\n   SELECT  1  "
        body_b = "CREATE PROCEDURE sp_Test AS SELECT 1"

        assert hash_body(body_a) == hash_body(body_b)

        # And that actual content changes DO produce different hashes
        body_c = "CREATE PROCEDURE sp_Test AS SELECT 2"
        assert hash_body(body_a) != hash_body(body_c)
