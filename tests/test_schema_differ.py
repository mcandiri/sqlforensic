"""Tests for schema_differ.py and diff_result.py data structures."""

from __future__ import annotations

from sqlforensic.diff.diff_result import (
    ColumnInfo,
    ColumnModification,
    DiffResult,
    ForeignKeyInfo,
    TableDiff,
    TableInfo,
    TableModification,
)
from sqlforensic.diff.schema_differ import diff_foreign_keys, diff_tables

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

SOURCE_TABLES = [
    {
        "TABLE_SCHEMA": "dbo",
        "TABLE_NAME": "Students",
        "row_count": 15000,
        "columns": [
            {
                "COLUMN_NAME": "Id",
                "DATA_TYPE": "int",
                "CHARACTER_MAXIMUM_LENGTH": None,
                "IS_NULLABLE": "NO",
                "COLUMN_DEFAULT": None,
                "ORDINAL_POSITION": 1,
                "is_primary_key": 1,
            },
            {
                "COLUMN_NAME": "FirstName",
                "DATA_TYPE": "varchar",
                "CHARACTER_MAXIMUM_LENGTH": 100,
                "IS_NULLABLE": "NO",
                "COLUMN_DEFAULT": None,
                "ORDINAL_POSITION": 2,
                "is_primary_key": 0,
            },
            {
                "COLUMN_NAME": "Email",
                "DATA_TYPE": "varchar",
                "CHARACTER_MAXIMUM_LENGTH": 100,
                "IS_NULLABLE": "NO",
                "COLUMN_DEFAULT": None,
                "ORDINAL_POSITION": 3,
                "is_primary_key": 0,
            },
            {
                "COLUMN_NAME": "MiddleName",
                "DATA_TYPE": "varchar",
                "CHARACTER_MAXIMUM_LENGTH": 50,
                "IS_NULLABLE": "YES",
                "COLUMN_DEFAULT": None,
                "ORDINAL_POSITION": 4,
                "is_primary_key": 0,
            },
        ],
    },
]

TARGET_TABLES = [
    {
        "TABLE_SCHEMA": "dbo",
        "TABLE_NAME": "Students",
        "row_count": 15000,
        "columns": [
            {
                "COLUMN_NAME": "Id",
                "DATA_TYPE": "int",
                "CHARACTER_MAXIMUM_LENGTH": None,
                "IS_NULLABLE": "NO",
                "COLUMN_DEFAULT": None,
                "ORDINAL_POSITION": 1,
                "is_primary_key": 1,
            },
            {
                "COLUMN_NAME": "FirstName",
                "DATA_TYPE": "varchar",
                "CHARACTER_MAXIMUM_LENGTH": 100,
                "IS_NULLABLE": "NO",
                "COLUMN_DEFAULT": None,
                "ORDINAL_POSITION": 2,
                "is_primary_key": 0,
            },
            {
                "COLUMN_NAME": "Email",
                "DATA_TYPE": "varchar",
                "CHARACTER_MAXIMUM_LENGTH": 200,
                "IS_NULLABLE": "YES",
                "COLUMN_DEFAULT": None,
                "ORDINAL_POSITION": 3,
                "is_primary_key": 0,
            },
            {
                "COLUMN_NAME": "LegacyCode",
                "DATA_TYPE": "varchar",
                "CHARACTER_MAXIMUM_LENGTH": 50,
                "IS_NULLABLE": "YES",
                "COLUMN_DEFAULT": None,
                "ORDINAL_POSITION": 4,
                "is_primary_key": 0,
            },
        ],
    },
]


# ---------------------------------------------------------------------------
# Tests — diff_tables
# ---------------------------------------------------------------------------


class TestSchemaDiffer:
    """Tests for the diff_tables function and related column diffing."""

    def test_identical_schemas_no_diff(self) -> None:
        """Identical tables on both sides should produce an empty TableDiff."""
        tables = [
            {
                "TABLE_SCHEMA": "dbo",
                "TABLE_NAME": "Users",
                "row_count": 100,
                "columns": [
                    {
                        "COLUMN_NAME": "Id",
                        "DATA_TYPE": "int",
                        "CHARACTER_MAXIMUM_LENGTH": None,
                        "IS_NULLABLE": "NO",
                        "COLUMN_DEFAULT": None,
                        "ORDINAL_POSITION": 1,
                        "is_primary_key": 1,
                    },
                ],
            },
        ]

        result = diff_tables(tables, tables)

        assert result.added_tables == []
        assert result.removed_tables == []
        assert result.modified_tables == []

    def test_added_table(self) -> None:
        """A table that exists only in source should appear in added_tables."""
        source = [
            {
                "TABLE_SCHEMA": "dbo",
                "TABLE_NAME": "NewTable",
                "row_count": 0,
                "columns": [
                    {
                        "COLUMN_NAME": "Id",
                        "DATA_TYPE": "int",
                        "CHARACTER_MAXIMUM_LENGTH": None,
                        "IS_NULLABLE": "NO",
                        "COLUMN_DEFAULT": None,
                        "ORDINAL_POSITION": 1,
                        "is_primary_key": 1,
                    },
                ],
            },
        ]
        target: list[dict] = []

        result = diff_tables(source, target)

        assert len(result.added_tables) == 1
        assert result.added_tables[0].name == "NewTable"
        assert result.removed_tables == []

    def test_removed_table(self) -> None:
        """A table that exists only in target should appear in removed_tables."""
        source: list[dict] = []
        target = [
            {
                "TABLE_SCHEMA": "dbo",
                "TABLE_NAME": "OldTable",
                "row_count": 500,
                "columns": [
                    {
                        "COLUMN_NAME": "Id",
                        "DATA_TYPE": "int",
                        "CHARACTER_MAXIMUM_LENGTH": None,
                        "IS_NULLABLE": "NO",
                        "COLUMN_DEFAULT": None,
                        "ORDINAL_POSITION": 1,
                        "is_primary_key": 1,
                    },
                ],
            },
        ]

        result = diff_tables(source, target)

        assert len(result.removed_tables) == 1
        assert result.removed_tables[0].name == "OldTable"
        assert result.added_tables == []

    def test_added_column(self) -> None:
        """Source has an extra column -- it should appear in added_columns."""
        result = diff_tables(SOURCE_TABLES, TARGET_TABLES)

        assert len(result.modified_tables) == 1
        mod = result.modified_tables[0]
        added_names = [c.name for c in mod.added_columns]
        assert "MiddleName" in added_names

    def test_removed_column(self) -> None:
        """Target has an extra column -- it should appear in removed_columns."""
        result = diff_tables(SOURCE_TABLES, TARGET_TABLES)

        mod = result.modified_tables[0]
        removed_names = [c.name for c in mod.removed_columns]
        assert "LegacyCode" in removed_names

    def test_type_change(self) -> None:
        """A column whose DATA_TYPE differs should produce a type_change modification."""
        source = [
            {
                "TABLE_SCHEMA": "dbo",
                "TABLE_NAME": "T",
                "row_count": 0,
                "columns": [
                    {
                        "COLUMN_NAME": "Val",
                        "DATA_TYPE": "bigint",
                        "CHARACTER_MAXIMUM_LENGTH": None,
                        "IS_NULLABLE": "NO",
                        "COLUMN_DEFAULT": None,
                        "ORDINAL_POSITION": 1,
                        "is_primary_key": 0,
                    },
                ],
            },
        ]
        target = [
            {
                "TABLE_SCHEMA": "dbo",
                "TABLE_NAME": "T",
                "row_count": 0,
                "columns": [
                    {
                        "COLUMN_NAME": "Val",
                        "DATA_TYPE": "int",
                        "CHARACTER_MAXIMUM_LENGTH": None,
                        "IS_NULLABLE": "NO",
                        "COLUMN_DEFAULT": None,
                        "ORDINAL_POSITION": 1,
                        "is_primary_key": 0,
                    },
                ],
            },
        ]

        result = diff_tables(source, target)

        assert len(result.modified_tables) == 1
        mod = result.modified_tables[0]
        type_changes = [m for m in mod.modified_columns if m.change_type == "type_change"]
        assert len(type_changes) == 1
        assert type_changes[0].is_breaking is True
        assert type_changes[0].old_value == "int"
        assert type_changes[0].new_value == "bigint"

    def test_nullability_change(self) -> None:
        """YES->NO is breaking; NO->YES is not breaking."""
        # Source: Email is NOT NULL (NO), Target: Email is NULL (YES)
        result = diff_tables(SOURCE_TABLES, TARGET_TABLES)

        mod = result.modified_tables[0]
        null_mods = [m for m in mod.modified_columns if m.change_type == "nullability_change"]
        assert len(null_mods) == 1
        # Source says NO (not null), target says YES (nullable) => becoming NOT NULL => breaking
        email_mod = null_mods[0]
        assert email_mod.column_name == "Email"
        assert email_mod.is_breaking is True  # YES -> NO is breaking
        assert email_mod.new_value == "NO"
        assert email_mod.old_value == "YES"

        # Now test the other direction: NO->YES should not be breaking
        source_no = [
            {
                "TABLE_SCHEMA": "dbo",
                "TABLE_NAME": "T",
                "row_count": 0,
                "columns": [
                    {
                        "COLUMN_NAME": "Col",
                        "DATA_TYPE": "int",
                        "CHARACTER_MAXIMUM_LENGTH": None,
                        "IS_NULLABLE": "YES",
                        "COLUMN_DEFAULT": None,
                        "ORDINAL_POSITION": 1,
                        "is_primary_key": 0,
                    },
                ],
            },
        ]
        target_no = [
            {
                "TABLE_SCHEMA": "dbo",
                "TABLE_NAME": "T",
                "row_count": 0,
                "columns": [
                    {
                        "COLUMN_NAME": "Col",
                        "DATA_TYPE": "int",
                        "CHARACTER_MAXIMUM_LENGTH": None,
                        "IS_NULLABLE": "NO",
                        "COLUMN_DEFAULT": None,
                        "ORDINAL_POSITION": 1,
                        "is_primary_key": 0,
                    },
                ],
            },
        ]

        result2 = diff_tables(source_no, target_no)
        mod2 = result2.modified_tables[0]
        null_mods2 = [m for m in mod2.modified_columns if m.change_type == "nullability_change"]
        assert len(null_mods2) == 1
        assert null_mods2[0].is_breaking is False  # NO -> YES (becoming nullable) is not breaking

    def test_length_change_shrink(self) -> None:
        """Shrinking a column length should be marked as is_breaking=True."""
        # In SOURCE_TABLES Email has length 100, in TARGET_TABLES it has 200.
        # Source wants 100, target has 200 => that is a shrink => breaking.
        result = diff_tables(SOURCE_TABLES, TARGET_TABLES)

        mod = result.modified_tables[0]
        len_mods = [m for m in mod.modified_columns if m.change_type == "length_change"]
        assert len(len_mods) == 1
        assert len_mods[0].column_name == "Email"
        assert len_mods[0].is_breaking is True  # 100 < 200 => shrink

    def test_default_change(self) -> None:
        """Changing a column default should produce a non-breaking change."""
        source = [
            {
                "TABLE_SCHEMA": "dbo",
                "TABLE_NAME": "T",
                "row_count": 0,
                "columns": [
                    {
                        "COLUMN_NAME": "Status",
                        "DATA_TYPE": "int",
                        "CHARACTER_MAXIMUM_LENGTH": None,
                        "IS_NULLABLE": "YES",
                        "COLUMN_DEFAULT": "1",
                        "ORDINAL_POSITION": 1,
                        "is_primary_key": 0,
                    },
                ],
            },
        ]
        target = [
            {
                "TABLE_SCHEMA": "dbo",
                "TABLE_NAME": "T",
                "row_count": 0,
                "columns": [
                    {
                        "COLUMN_NAME": "Status",
                        "DATA_TYPE": "int",
                        "CHARACTER_MAXIMUM_LENGTH": None,
                        "IS_NULLABLE": "YES",
                        "COLUMN_DEFAULT": "0",
                        "ORDINAL_POSITION": 1,
                        "is_primary_key": 0,
                    },
                ],
            },
        ]

        result = diff_tables(source, target)

        mod = result.modified_tables[0]
        default_mods = [m for m in mod.modified_columns if m.change_type == "default_change"]
        assert len(default_mods) == 1
        assert default_mods[0].is_breaking is False

    def test_foreign_key_diff(self) -> None:
        """Added and removed foreign keys should be detected."""
        source_fks = [
            {
                "constraint_name": "FK_New",
                "parent_schema": "dbo",
                "parent_table": "Orders",
                "parent_column": "CustomerId",
                "referenced_schema": "dbo",
                "referenced_table": "Customers",
                "referenced_column": "Id",
            },
        ]
        target_fks = [
            {
                "constraint_name": "FK_Old",
                "parent_schema": "dbo",
                "parent_table": "Invoices",
                "parent_column": "OrderId",
                "referenced_schema": "dbo",
                "referenced_table": "Orders",
                "referenced_column": "Id",
            },
        ]

        added, removed = diff_foreign_keys(source_fks, target_fks)

        assert len(added) == 1
        assert added[0].parent_table == "Orders"
        assert len(removed) == 1
        assert removed[0].parent_table == "Invoices"


# ---------------------------------------------------------------------------
# Tests — DiffResult data class
# ---------------------------------------------------------------------------


class TestDiffResult:
    """Tests for DiffResult summary, total_changes, has_changes properties."""

    def test_diff_result_summary(self) -> None:
        """summary property should return correct counts per category."""
        diff = DiffResult(
            tables=TableDiff(
                added_tables=[TableInfo(name="A")],
                removed_tables=[],
                modified_tables=[
                    TableModification(
                        table_name="X",
                        added_columns=[ColumnInfo(name="c1")],
                        removed_columns=[ColumnInfo(name="c2"), ColumnInfo(name="c3")],
                        modified_columns=[
                            ColumnModification(column_name="c4", change_type="type_change"),
                        ],
                    ),
                ],
            ),
        )

        s = diff.summary
        assert s["Tables"]["Added"] == 1
        assert s["Tables"]["Removed"] == 0
        assert s["Tables"]["Modified"] == 1
        assert s["Columns"]["Added"] == 1
        assert s["Columns"]["Removed"] == 2
        assert s["Columns"]["Modified"] == 1

    def test_diff_result_total_changes(self) -> None:
        """total_changes should sum all categories."""
        diff = DiffResult(
            tables=TableDiff(
                added_tables=[TableInfo(name="A"), TableInfo(name="B")],
                removed_tables=[TableInfo(name="C")],
                modified_tables=[],
            ),
            foreign_keys_added=[ForeignKeyInfo(constraint_name="FK1")],
        )

        # 2 added + 1 removed + 0 modified + 1 FK added = 4
        assert diff.total_changes == 4

    def test_diff_result_has_changes(self) -> None:
        """has_changes should be True when changes exist, False when empty."""
        empty = DiffResult()
        assert empty.has_changes is False

        non_empty = DiffResult(
            tables=TableDiff(added_tables=[TableInfo(name="T")]),
        )
        assert non_empty.has_changes is True
