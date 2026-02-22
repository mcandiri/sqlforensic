"""Tests for migration_generator.py — SQL migration script generation."""

from __future__ import annotations

from sqlforensic.diff.diff_result import (
    ColumnInfo,
    ColumnModification,
    DiffResult,
    ForeignKeyInfo,
    RiskAssessment,
    TableDiff,
    TableInfo,
    TableModification,
)
from sqlforensic.diff.migration_generator import MigrationGenerator

# ---------------------------------------------------------------------------
# Helper to build a simple DiffResult
# ---------------------------------------------------------------------------


def _empty_diff(**overrides) -> DiffResult:
    """Return a DiffResult with sensible defaults, then apply overrides."""
    defaults = dict(
        source_database="SourceDB",
        target_database="TargetDB",
        source_server="src-server",
        target_server="tgt-server",
        provider="sqlserver",
    )
    defaults.update(overrides)
    return DiffResult(**defaults)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMigrationGenerator:
    """Tests for MigrationGenerator.generate()."""

    def test_empty_diff_no_migration(self) -> None:
        """An empty DiffResult should produce a script with only header and footer."""
        diff = _empty_diff()
        gen = MigrationGenerator(diff, provider="sqlserver", safe_mode=True)
        script = gen.generate()

        assert "SQLForensic Migration Script" in script
        assert "End of migration script" in script
        # No step headers should be emitted for an empty diff
        assert "Step 1:" not in script

    def test_create_table_in_script(self) -> None:
        """An added table should produce a CREATE TABLE statement."""
        diff = _empty_diff(
            tables=TableDiff(
                added_tables=[
                    TableInfo(
                        schema="dbo",
                        name="Products",
                        columns=[
                            ColumnInfo(
                                name="Id", data_type="int", is_nullable=False, is_primary_key=True
                            ),
                            ColumnInfo(
                                name="Name", data_type="varchar", max_length=100, is_nullable=False
                            ),
                        ],
                        row_count=0,
                    ),
                ],
            ),
        )
        gen = MigrationGenerator(diff, provider="sqlserver", safe_mode=True)
        script = gen.generate()

        assert "CREATE TABLE" in script
        assert "Products" in script

    def test_add_column_in_script(self) -> None:
        """An added column should appear as ALTER TABLE ADD."""
        diff = _empty_diff(
            tables=TableDiff(
                modified_tables=[
                    TableModification(
                        table_name="Orders",
                        table_schema="dbo",
                        added_columns=[
                            ColumnInfo(
                                name="TrackingCode",
                                data_type="varchar",
                                max_length=50,
                                is_nullable=True,
                            ),
                        ],
                    ),
                ],
            ),
        )
        gen = MigrationGenerator(diff, provider="sqlserver", safe_mode=True)
        script = gen.generate()

        assert "ALTER TABLE" in script
        assert "ADD" in script
        assert "TrackingCode" in script

    def test_safe_mode_comments_drops(self) -> None:
        """In safe_mode, DROP TABLE and DROP COLUMN should be commented out."""
        diff = _empty_diff(
            tables=TableDiff(
                removed_tables=[
                    TableInfo(schema="dbo", name="OldTable", columns=[], row_count=0),
                ],
                modified_tables=[
                    TableModification(
                        table_name="Users",
                        table_schema="dbo",
                        removed_columns=[
                            ColumnInfo(name="LegacyCol", data_type="varchar", max_length=50),
                        ],
                    ),
                ],
            ),
        )
        gen = MigrationGenerator(diff, provider="sqlserver", safe_mode=True)
        script = gen.generate()

        assert "MANUAL REVIEW REQUIRED" in script
        # Drop statements should be commented out
        lines = script.split("\n")
        drop_tbl = [x for x in lines if "DROP TABLE" in x and "OldTable" in x]
        assert all(x.strip().startswith("--") for x in drop_tbl)

        drop_col = [x for x in lines if "DROP COLUMN" in x and "LegacyCol" in x]
        assert all(x.strip().startswith("--") for x in drop_col)

    def test_unsafe_mode_active_drops(self) -> None:
        """Without safe_mode, DROP statements should be active SQL (not commented)."""
        diff = _empty_diff(
            tables=TableDiff(
                removed_tables=[
                    TableInfo(schema="dbo", name="OldTable", columns=[], row_count=0),
                ],
                modified_tables=[
                    TableModification(
                        table_name="Users",
                        table_schema="dbo",
                        removed_columns=[
                            ColumnInfo(name="LegacyCol", data_type="varchar", max_length=50),
                        ],
                    ),
                ],
            ),
        )
        gen = MigrationGenerator(diff, provider="sqlserver", safe_mode=False)
        script = gen.generate()

        lines = script.split("\n")
        # At least one active DROP TABLE statement
        drop_tbl = [x for x in lines if "DROP TABLE" in x and "OldTable" in x]
        assert any(not x.strip().startswith("--") for x in drop_tbl)

        # At least one active DROP COLUMN statement
        drop_col = [x for x in lines if "DROP COLUMN" in x and "LegacyCol" in x]
        assert any(not x.strip().startswith("--") for x in drop_col)

    def test_postgresql_syntax(self) -> None:
        """PostgreSQL provider should use double quotes, RAISE NOTICE, and BEGIN/COMMIT."""
        diff = _empty_diff(
            provider="postgresql",
            tables=TableDiff(
                added_tables=[
                    TableInfo(
                        schema="public",
                        name="Items",
                        columns=[
                            ColumnInfo(
                                name="Id", data_type="int", is_nullable=False, is_primary_key=True
                            ),
                        ],
                        row_count=0,
                    ),
                ],
            ),
        )
        gen = MigrationGenerator(diff, provider="postgresql", safe_mode=False)
        script = gen.generate()

        assert "BEGIN;" in script
        assert "COMMIT;" in script
        assert "RAISE NOTICE" in script
        # Double-quoted identifiers
        assert '"public"' in script or '"Items"' in script

    def test_sqlserver_syntax(self) -> None:
        """SQL Server provider should use brackets, PRINT, and BEGIN TRY pattern."""
        diff = _empty_diff(
            provider="sqlserver",
            tables=TableDiff(
                added_tables=[
                    TableInfo(
                        schema="dbo",
                        name="Items",
                        columns=[
                            ColumnInfo(
                                name="Id", data_type="int", is_nullable=False, is_primary_key=True
                            ),
                        ],
                        row_count=0,
                    ),
                ],
            ),
        )
        gen = MigrationGenerator(diff, provider="sqlserver", safe_mode=True)
        script = gen.generate()

        assert "BEGIN TRY" in script
        assert "END TRY" in script
        assert "BEGIN CATCH" in script
        assert "END CATCH" in script
        assert "PRINT" in script
        # Bracket-quoted identifiers
        assert "[dbo]" in script
        assert "[Items]" in script

    def test_fk_add_in_script(self) -> None:
        """Added foreign keys should appear as ADD CONSTRAINT ... FOREIGN KEY."""
        diff = _empty_diff(
            foreign_keys_added=[
                ForeignKeyInfo(
                    constraint_name="FK_Orders_Customers",
                    parent_schema="dbo",
                    parent_table="Orders",
                    parent_column="CustomerId",
                    referenced_schema="dbo",
                    referenced_table="Customers",
                    referenced_column="Id",
                ),
            ],
        )
        gen = MigrationGenerator(diff, provider="sqlserver", safe_mode=True)
        script = gen.generate()

        assert "ADD CONSTRAINT" in script
        assert "FOREIGN KEY" in script
        assert "FK_Orders_Customers" in script

    def test_type_change_in_script(self) -> None:
        """Column type changes should produce ALTER COLUMN statements."""
        diff = _empty_diff(
            tables=TableDiff(
                modified_tables=[
                    TableModification(
                        table_name="Users",
                        table_schema="dbo",
                        modified_columns=[
                            ColumnModification(
                                column_name="Status",
                                change_type="type_change",
                                old_value="int",
                                new_value="bigint",
                                is_breaking=True,
                            ),
                        ],
                    ),
                ],
            ),
        )
        gen = MigrationGenerator(diff, provider="sqlserver", safe_mode=True)
        script = gen.generate()

        assert "ALTER TABLE" in script
        assert "ALTER COLUMN" in script
        assert "Status" in script
        assert "bigint" in script

    def test_risk_warnings_in_comments(self) -> None:
        """Risky changes should have warning comments in the output."""
        diff = _empty_diff(
            tables=TableDiff(
                removed_tables=[
                    TableInfo(schema="dbo", name="CriticalTable", columns=[], row_count=10000),
                ],
            ),
            risks=[
                RiskAssessment(
                    change_description="DROP TABLE dbo.CriticalTable",
                    table="CriticalTable",
                    risk_score=0.8,
                    risk_level="CRITICAL",
                    breaking_changes=["Table CriticalTable will be permanently removed"],
                    recommendations=["Backup before dropping"],
                ),
            ],
            risk_level="CRITICAL",
        )
        gen = MigrationGenerator(diff, provider="sqlserver", safe_mode=True)
        script = gen.generate()

        assert "RISK [CRITICAL]" in script
        assert "Breaking:" in script
        assert "CriticalTable" in script
