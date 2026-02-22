"""Migration script generator from schema diff results."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlforensic.diff.diff_result import (
    ColumnInfo,
    DiffResult,
)

logger = logging.getLogger(__name__)


def _quote_identifier(name: str, provider: str = "sqlserver") -> str:
    """Quote an identifier for the given database provider.

    Args:
        name: The identifier to quote.
        provider: Database provider ('sqlserver' or 'postgresql').

    Returns:
        Quoted identifier string.
    """
    if provider == "postgresql":
        return f'"{name}"'
    return f"[{name}]"


def _qualified_name(schema: str, name: str, provider: str = "sqlserver") -> str:
    """Build a fully qualified [schema].[name] identifier.

    Args:
        schema: Schema name.
        name: Object name.
        provider: Database provider.

    Returns:
        Fully qualified quoted identifier.
    """
    q = _quote_identifier
    return f"{q(schema, provider)}.{q(name, provider)}"


class MigrationGenerator:
    """Generate migration SQL scripts from a DiffResult.

    Produces an ordered, safe migration script with transaction wrapping,
    existence checks, risk warnings, and optional safe-mode protections
    for destructive changes.

    Args:
        diff: The schema diff result to generate migration for.
        provider: Database provider ('sqlserver' or 'postgresql').
        safe_mode: When True, destructive operations (column drops, table drops)
                   are commented out and flagged for manual review.
    """

    def __init__(
        self,
        diff: DiffResult,
        provider: str = "sqlserver",
        safe_mode: bool = True,
    ) -> None:
        self.diff = diff
        self.provider = provider
        self.safe_mode = safe_mode
        self._lines: list[str] = []
        self._step = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self) -> str:
        """Generate the full migration SQL script.

        Ordered steps:
            1. Create new tables
            2. Add new columns
            3. Modify columns (type, nullability, length)
            4. Add new constraints / foreign keys
            5. Create/modify SPs and views (flagged as comments)
            6. Drop removed constraints / foreign keys
            7. Drop removed columns (commented out in safe_mode for CRITICAL)
            8. Drop removed tables (commented out in safe_mode)

        Safe mode wraps everything in a transaction with error handling
        and comments out breaking changes for manual review.

        Returns:
            Complete migration SQL script as a string.
        """
        logger.info(
            "Generating migration script (provider=%s, safe_mode=%s)",
            self.provider,
            self.safe_mode,
        )

        self._lines = []
        self._step = 0

        self._emit_header()
        self._begin_transaction()

        # Step 1 — Create new tables
        self._step_create_tables()

        # Step 2 — Add new columns
        self._step_add_columns()

        # Step 3 — Modify columns
        self._step_modify_columns()

        # Step 4 — Add constraints and foreign keys
        self._step_add_constraints()

        # Step 5 — SPs, views, and functions (comments only)
        self._step_programmable_objects()

        # Step 6 — Drop removed constraints / foreign keys
        self._step_drop_constraints()

        # Step 7 — Drop removed columns
        self._step_drop_columns()

        # Step 8 — Drop removed tables
        self._step_drop_tables()

        self._end_transaction()
        self._emit_footer()

        script = "\n".join(self._lines)
        logger.info("Migration script generated (%d lines)", len(self._lines))
        return script

    # ------------------------------------------------------------------
    # Header / footer
    # ------------------------------------------------------------------

    def _emit_header(self) -> None:
        """Emit the script header with metadata."""
        now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        self._w("-- ============================================================")
        self._w("-- SQLForensic Migration Script")
        self._w(f"-- Generated: {now}")
        self._w(f"-- Provider:  {self.provider}")
        self._w(f"-- Source:    {self.diff.source_server}/{self.diff.source_database}")
        self._w(f"-- Target:    {self.diff.target_server}/{self.diff.target_database}")
        self._w(f"-- Safe mode: {'ON' if self.safe_mode else 'OFF'}")
        self._w(f"-- Risk level: {self.diff.risk_level}")
        self._w(f"-- Total changes: {self.diff.total_changes}")
        self._w("-- ============================================================")
        self._w("")

        if self.diff.risks:
            self._w("-- RISK SUMMARY:")
            for risk in self.diff.risks:
                if risk.risk_level in ("HIGH", "CRITICAL"):
                    self._w(f"--   [{risk.risk_level}] {risk.change_description}")
                    for bc in risk.breaking_changes:
                        self._w(f"--          ^ {bc}")
            self._w("")

    def _emit_footer(self) -> None:
        """Emit the script footer."""
        self._w("")
        self._w("-- ============================================================")
        self._w("-- End of migration script")
        self._w("-- ============================================================")

    # ------------------------------------------------------------------
    # Transaction wrapper
    # ------------------------------------------------------------------

    def _begin_transaction(self) -> None:
        """Emit transaction start with error handling."""
        if self.provider == "postgresql":
            self._w("BEGIN;")
            self._w("")
        else:
            self._w("BEGIN TRY")
            self._w("    BEGIN TRANSACTION;")
            self._w("")
            self._print_msg("Starting migration...")
            self._w("")

    def _end_transaction(self) -> None:
        """Emit transaction commit / rollback."""
        self._w("")
        if self.provider == "postgresql":
            self._w("COMMIT;")
        else:
            self._w("    COMMIT TRANSACTION;")
            self._print_msg("Migration completed successfully.")
            self._w("END TRY")
            self._w("BEGIN CATCH")
            self._w("    ROLLBACK TRANSACTION;")
            self._print_msg("Migration FAILED. Transaction rolled back. Error: ' + ERROR_MESSAGE()")
            self._w("    THROW;")
            self._w("END CATCH")

    # ------------------------------------------------------------------
    # Step 1 — Create new tables
    # ------------------------------------------------------------------

    def _step_create_tables(self) -> None:
        """Generate CREATE TABLE statements for added tables."""
        tables = self.diff.tables.added_tables
        if not tables:
            return

        self._next_step("Create new tables")
        for table in tables:
            self._emit_risk_warnings(table.name)
            full = _qualified_name(table.schema or "dbo", table.name, self.provider)
            self._w(
                f"IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLES "
                f"WHERE TABLE_SCHEMA = '{table.schema or 'dbo'}' "
                f"AND TABLE_NAME = '{table.name}')"
            )
            self._w("BEGIN")
            self._w(f"    CREATE TABLE {full} (")
            col_defs: list[str] = []
            pk_cols: list[str] = []
            for col in table.columns:
                col_defs.append(f"        {self._column_definition(col)}")
                if col.is_primary_key:
                    pk_cols.append(col.name)
            if pk_cols:
                pk_list = ", ".join(_quote_identifier(c, self.provider) for c in pk_cols)
                col_defs.append(f"        CONSTRAINT PK_{table.name} PRIMARY KEY ({pk_list})")
            self._w(",\n".join(col_defs))
            self._w("    );")
            self._print_msg(f"Created table {full}")
            self._w("END")
            self._w("")

    # ------------------------------------------------------------------
    # Step 2 — Add new columns
    # ------------------------------------------------------------------

    def _step_add_columns(self) -> None:
        """Generate ALTER TABLE ADD COLUMN for new columns."""
        mods_with_adds = [m for m in self.diff.tables.modified_tables if m.added_columns]
        if not mods_with_adds:
            return

        self._next_step("Add new columns")
        for mod in mods_with_adds:
            full = _qualified_name(mod.table_schema or "dbo", mod.table_name, self.provider)
            for col in mod.added_columns:
                col_q = _quote_identifier(col.name, self.provider)
                self._w(
                    f"IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS "
                    f"WHERE TABLE_SCHEMA = '{mod.table_schema or 'dbo'}' "
                    f"AND TABLE_NAME = '{mod.table_name}' "
                    f"AND COLUMN_NAME = '{col.name}')"
                )
                self._w("BEGIN")
                self._w(
                    f"    ALTER TABLE {full} ADD {col_q} "
                    f"{self._type_spec(col)}{self._null_spec(col)}{self._default_spec(col)};"
                )
                self._print_msg(f"Added column {col.name} to {full}")
                self._w("END")
                self._w("")

    # ------------------------------------------------------------------
    # Step 3 — Modify columns
    # ------------------------------------------------------------------

    def _step_modify_columns(self) -> None:
        """Generate ALTER COLUMN for type, nullability, and length changes."""
        mods_with_changes = [m for m in self.diff.tables.modified_tables if m.modified_columns]
        if not mods_with_changes:
            return

        self._next_step("Modify existing columns")
        for mod in mods_with_changes:
            full = _qualified_name(mod.table_schema or "dbo", mod.table_name, self.provider)
            for col_mod in mod.modified_columns:
                self._emit_risk_warnings(mod.table_name, col_mod.column_name)
                if col_mod.is_breaking:
                    self._w(
                        f"-- WARNING: Breaking change on {mod.table_name}.{col_mod.column_name}"
                    )
                    self._w(
                        f"--   {col_mod.change_type}: {col_mod.old_value} -> {col_mod.new_value}"
                    )

                col_q = _quote_identifier(col_mod.column_name, self.provider)

                if col_mod.change_type in ("type_change", "length_change"):
                    new_type = col_mod.new_value
                    if col_mod.change_type == "length_change":
                        # For length changes, we need to rebuild the type spec
                        # new_value holds the new length
                        new_type = f"({col_mod.new_value})"
                        self._w(
                            f"-- NOTE: Adjust the type below to match the full "
                            f"data type with new length {col_mod.new_value}"
                        )

                    if self.provider == "postgresql":
                        self._w(f"ALTER TABLE {full} ALTER COLUMN {col_q} TYPE {new_type};")
                    else:
                        self._w(f"ALTER TABLE {full} ALTER COLUMN {col_q} {new_type};")

                elif col_mod.change_type == "nullability_change":
                    null_kw = "NULL" if col_mod.new_value == "YES" else "NOT NULL"
                    if self.provider == "postgresql":
                        if null_kw == "NOT NULL":
                            self._w(f"ALTER TABLE {full} ALTER COLUMN {col_q} SET NOT NULL;")
                        else:
                            self._w(f"ALTER TABLE {full} ALTER COLUMN {col_q} DROP NOT NULL;")
                    else:
                        # SQL Server needs the full type re-specified; flag it
                        self._w(
                            "-- NOTE: SQL Server ALTER COLUMN requires the full "
                            "data type. Adjust as needed."
                        )
                        self._w(
                            f"ALTER TABLE {full} ALTER COLUMN {col_q} /* <data_type> */ {null_kw};"
                        )

                elif col_mod.change_type == "default_change":
                    if self.provider == "postgresql":
                        if col_mod.new_value:
                            self._w(
                                f"ALTER TABLE {full} ALTER COLUMN {col_q} "
                                f"SET DEFAULT {col_mod.new_value};"
                            )
                        else:
                            self._w(f"ALTER TABLE {full} ALTER COLUMN {col_q} DROP DEFAULT;")
                    else:
                        # SQL Server default handling via constraints
                        self._w(
                            "-- NOTE: SQL Server defaults are managed via "
                            "constraints. Manual review may be required."
                        )
                        if col_mod.new_value:
                            df_name = f"DF_{mod.table_name}_{col_mod.column_name}"
                            self._w(
                                f"ALTER TABLE {full} ADD CONSTRAINT "
                                f"{_quote_identifier(df_name, self.provider)} "
                                f"DEFAULT {col_mod.new_value} FOR {col_q};"
                            )
                        else:
                            self._w(f"-- Drop existing default constraint on {col_q} manually")
                self._w("")

    # ------------------------------------------------------------------
    # Step 4 — Add constraints / foreign keys
    # ------------------------------------------------------------------

    def _step_add_constraints(self) -> None:
        """Generate ADD CONSTRAINT for new constraints and foreign keys."""
        added_fks = self.diff.foreign_keys_added
        mods_with_constraints = [m for m in self.diff.tables.modified_tables if m.added_constraints]
        if not added_fks and not mods_with_constraints:
            return

        self._next_step("Add new constraints and foreign keys")

        # Table-level constraints (PK, UNIQUE, CHECK)
        for mod in mods_with_constraints:
            full = _qualified_name(mod.table_schema or "dbo", mod.table_name, self.provider)
            for cons in mod.added_constraints:
                col_list = ", ".join(_quote_identifier(c, self.provider) for c in cons.columns)
                self._w(
                    f"ALTER TABLE {full} ADD CONSTRAINT "
                    f"{_quote_identifier(cons.name, self.provider)} "
                    f"{cons.constraint_type} ({col_list});"
                )
                self._print_msg(f"Added constraint {cons.name} on {mod.table_name}")
                self._w("")

        # Foreign keys
        for fk in added_fks:
            parent_full = _qualified_name(fk.parent_schema or "dbo", fk.parent_table, self.provider)
            ref_full = _qualified_name(
                fk.referenced_schema or "dbo",
                fk.referenced_table,
                self.provider,
            )
            parent_col = _quote_identifier(fk.parent_column, self.provider)
            ref_col = _quote_identifier(fk.referenced_column, self.provider)
            fk_name = fk.constraint_name or (
                f"FK_{fk.parent_table}_{fk.parent_column}_"
                f"{fk.referenced_table}_{fk.referenced_column}"
            )
            self._w(
                f"IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS "
                f"WHERE CONSTRAINT_NAME = '{fk_name}')"
            )
            self._w("BEGIN")
            self._w(
                f"    ALTER TABLE {parent_full} ADD CONSTRAINT "
                f"{_quote_identifier(fk_name, self.provider)} "
                f"FOREIGN KEY ({parent_col}) "
                f"REFERENCES {ref_full} ({ref_col});"
            )
            self._print_msg(
                f"Added foreign key {fk_name} "
                f"({fk.parent_table}.{fk.parent_column} -> "
                f"{fk.referenced_table}.{fk.referenced_column})"
            )
            self._w("END")
            self._w("")

    # ------------------------------------------------------------------
    # Step 5 — Programmable objects (SPs, views, functions)
    # ------------------------------------------------------------------

    def _step_programmable_objects(self) -> None:
        """Flag SP, view, and function changes as comments for manual action."""
        procs = self.diff.procedures
        views = self.diff.views
        funcs = self.diff.functions

        has_changes = (
            procs.added
            or procs.removed
            or procs.modified
            or views.added
            or views.removed
            or views.modified
            or funcs.added
            or funcs.removed
            or funcs.modified
        )
        if not has_changes:
            return

        self._next_step("Programmable objects (manual review required)")
        self._w("-- NOTE: Stored procedures, views, and functions require")
        self._w("-- manual review. Their bodies are not included in this script.")
        self._w("")

        for label, obj_diff, type_name in [
            ("Stored Procedures", procs, "PROCEDURE"),
            ("Views", views, "VIEW"),
            ("Functions", funcs, "FUNCTION"),
        ]:
            if obj_diff.added:
                self._w(f"-- New {label}:")
                for obj in obj_diff.added:
                    name = _qualified_name(
                        obj.get("schema", "dbo"),
                        obj.get("name", ""),
                        self.provider,
                    )
                    self._w(f"--   CREATE {type_name} {name}  -- TODO: add definition")
                self._w("")

            if obj_diff.removed:
                self._w(f"-- Removed {label}:")
                for obj in obj_diff.removed:
                    name = _qualified_name(
                        obj.get("schema", "dbo"),
                        obj.get("name", ""),
                        self.provider,
                    )
                    self._w(f"--   DROP {type_name} {name}  -- TODO: verify before dropping")
                self._w("")

            if obj_diff.modified:
                self._w(f"-- Modified {label}:")
                for mod_obj in obj_diff.modified:
                    name = _qualified_name(mod_obj.schema or "dbo", mod_obj.name, self.provider)
                    self._w(
                        f"--   ALTER {type_name} {name}  "
                        f"-- hash changed: {mod_obj.source_hash} -> {mod_obj.target_hash}"
                    )
                self._w("")

    # ------------------------------------------------------------------
    # Step 6 — Drop removed constraints / foreign keys
    # ------------------------------------------------------------------

    def _step_drop_constraints(self) -> None:
        """Generate DROP CONSTRAINT for removed FKs and constraints."""
        removed_fks = self.diff.foreign_keys_removed
        mods_with_drops = [m for m in self.diff.tables.modified_tables if m.removed_constraints]
        if not removed_fks and not mods_with_drops:
            return

        self._next_step("Drop removed constraints and foreign keys")

        # Table-level constraints
        for mod in mods_with_drops:
            full = _qualified_name(mod.table_schema or "dbo", mod.table_name, self.provider)
            for cons in mod.removed_constraints:
                self._w(
                    f"ALTER TABLE {full} DROP CONSTRAINT "
                    f"IF EXISTS {_quote_identifier(cons.name, self.provider)};"
                )
                self._print_msg(f"Dropped constraint {cons.name} from {mod.table_name}")
                self._w("")

        # Foreign keys
        for fk in removed_fks:
            self._emit_risk_warnings(fk.parent_table)
            parent_full = _qualified_name(fk.parent_schema or "dbo", fk.parent_table, self.provider)
            fk_name = fk.constraint_name or (
                f"FK_{fk.parent_table}_{fk.parent_column}_"
                f"{fk.referenced_table}_{fk.referenced_column}"
            )
            self._w(
                f"ALTER TABLE {parent_full} DROP CONSTRAINT "
                f"IF EXISTS {_quote_identifier(fk_name, self.provider)};"
            )
            self._print_msg(
                f"Dropped foreign key {fk_name} "
                f"({fk.parent_table}.{fk.parent_column} -> "
                f"{fk.referenced_table}.{fk.referenced_column})"
            )
            self._w("")

    # ------------------------------------------------------------------
    # Step 7 — Drop removed columns
    # ------------------------------------------------------------------

    def _step_drop_columns(self) -> None:
        """Generate ALTER TABLE DROP COLUMN for removed columns.

        In safe_mode, these statements are commented out with a
        MANUAL REVIEW REQUIRED warning.
        """
        mods_with_drops = [m for m in self.diff.tables.modified_tables if m.removed_columns]
        if not mods_with_drops:
            return

        self._next_step("Drop removed columns")
        if self.safe_mode:
            self._w("-- !! MANUAL REVIEW REQUIRED !!")
            self._w("-- The following DROP COLUMN statements are commented out for safety.")
            self._w("-- Uncomment ONLY after verifying no data loss will occur.")
            self._w("")

        for mod in mods_with_drops:
            full = _qualified_name(mod.table_schema or "dbo", mod.table_name, self.provider)
            for col in mod.removed_columns:
                self._emit_risk_warnings(mod.table_name, col.name)
                col_q = _quote_identifier(col.name, self.provider)
                stmt = f"ALTER TABLE {full} DROP COLUMN {col_q};"
                if self.safe_mode:
                    self._w(f"-- {stmt}")
                else:
                    self._w(stmt)
                    self._print_msg(f"Dropped column {col.name} from {mod.table_name}")
                self._w("")

    # ------------------------------------------------------------------
    # Step 8 — Drop removed tables
    # ------------------------------------------------------------------

    def _step_drop_tables(self) -> None:
        """Generate DROP TABLE for removed tables.

        In safe_mode, these statements are commented out with a
        MANUAL REVIEW REQUIRED warning.
        """
        tables = self.diff.tables.removed_tables
        if not tables:
            return

        self._next_step("Drop removed tables")
        if self.safe_mode:
            self._w("-- !! MANUAL REVIEW REQUIRED !!")
            self._w("-- The following DROP TABLE statements are commented out for safety.")
            self._w("-- Uncomment ONLY after verifying no dependent objects exist.")
            self._w("")

        for table in tables:
            self._emit_risk_warnings(table.name)
            full = _qualified_name(table.schema or "dbo", table.name, self.provider)
            stmt = f"DROP TABLE IF EXISTS {full};"
            if self.safe_mode:
                self._w(f"-- {stmt}")
            else:
                self._w(stmt)
                self._print_msg(f"Dropped table {full}")
            self._w("")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _next_step(self, title: str) -> None:
        """Emit a step header."""
        self._step += 1
        self._w("-- ----------------------------------------------------------")
        self._w(f"-- Step {self._step}: {title}")
        self._w("-- ----------------------------------------------------------")
        self._w("")

    def _w(self, line: str) -> None:
        """Append a line to the script output."""
        self._lines.append(line)

    def _print_msg(self, message: str) -> None:
        """Emit a provider-appropriate print/notice statement.

        Uses PRINT for SQL Server and RAISE NOTICE for PostgreSQL.
        """
        if self.provider == "postgresql":
            self._w(f"    RAISE NOTICE '{self._escape_sql(message)}';")
        else:
            self._w(f"    PRINT '{self._escape_sql(message)}';")

    def _column_definition(self, col: ColumnInfo) -> str:
        """Build a column definition clause for CREATE TABLE."""
        parts = [_quote_identifier(col.name, self.provider)]
        parts.append(self._type_spec(col))
        parts.append("NULL" if col.is_nullable else "NOT NULL")
        if col.default:
            parts.append(f"DEFAULT {col.default}")
        return " ".join(parts)

    def _type_spec(self, col: ColumnInfo) -> str:
        """Build the data type specification for a column."""
        dtype = col.data_type
        if col.max_length and col.max_length > 0:
            if col.max_length == -1:
                dtype = f"{dtype}(MAX)" if self.provider == "sqlserver" else f"{dtype}"
            else:
                dtype = f"{dtype}({col.max_length})"
        return dtype

    def _null_spec(self, col: ColumnInfo) -> str:
        """Return the NULL/NOT NULL specification for a column."""
        return " NULL" if col.is_nullable else " NOT NULL"

    def _default_spec(self, col: ColumnInfo) -> str:
        """Return the DEFAULT specification for a column, if any."""
        if col.default:
            return f" DEFAULT {col.default}"
        return ""

    def _emit_risk_warnings(self, table_name: str, column_name: str | None = None) -> None:
        """Emit SQL comments for any matching risk assessments."""
        for risk in self.diff.risks:
            if risk.table != table_name:
                continue
            if column_name and column_name not in risk.change_description:
                continue
            if risk.risk_level in ("HIGH", "CRITICAL"):
                self._w(f"-- RISK [{risk.risk_level}]: {risk.change_description}")
                for bc in risk.breaking_changes:
                    self._w(f"--   Breaking: {bc}")
                for rec in risk.recommendations:
                    self._w(f"--   Recommendation: {rec}")

    @staticmethod
    def _escape_sql(text: str) -> str:
        """Escape single quotes in SQL string literals."""
        return text.replace("'", "''")
