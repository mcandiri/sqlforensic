"""Table and column diff logic."""

from __future__ import annotations

from typing import Any

from sqlforensic.diff.diff_result import (
    ColumnInfo,
    ColumnModification,
    ForeignKeyInfo,
    TableDiff,
    TableInfo,
    TableModification,
)


def _build_column(raw: dict[str, Any]) -> ColumnInfo:
    """Build a ColumnInfo from a raw column dict."""
    return ColumnInfo(
        name=raw.get("COLUMN_NAME", ""),
        data_type=raw.get("DATA_TYPE", ""),
        max_length=raw.get("CHARACTER_MAXIMUM_LENGTH"),
        is_nullable=raw.get("IS_NULLABLE", "YES") == "YES",
        default=raw.get("COLUMN_DEFAULT"),
        ordinal=raw.get("ORDINAL_POSITION", 0),
        is_primary_key=bool(raw.get("is_primary_key")),
    )


def _build_table_info(table: dict[str, Any]) -> TableInfo:
    """Build a TableInfo from raw table dict with columns."""
    columns = [_build_column(c) for c in table.get("columns", [])]
    return TableInfo(
        schema=table.get("TABLE_SCHEMA", ""),
        name=table.get("TABLE_NAME", ""),
        columns=columns,
        row_count=table.get("row_count", 0) or 0,
    )


def _table_key(table: dict[str, Any]) -> str:
    """Build a lookup key for a table."""
    schema = table.get("TABLE_SCHEMA", "dbo")
    name = table.get("TABLE_NAME", "")
    return f"{schema}.{name}"


def _fk_key(fk: dict[str, Any]) -> str:
    """Build a lookup key for a foreign key."""
    return (
        f"{fk.get('parent_table', '')}.{fk.get('parent_column', '')}"
        f"→{fk.get('referenced_table', '')}.{fk.get('referenced_column', '')}"
    )


def diff_tables(
    source_tables: list[dict[str, Any]],
    target_tables: list[dict[str, Any]],
) -> TableDiff:
    """Compare source and target table lists.

    Args:
        source_tables: Tables from the source (desired state).
        target_tables: Tables from the target (current state).

    Returns:
        TableDiff with added, removed, and modified tables.
    """
    source_map = {_table_key(t): t for t in source_tables}
    target_map = {_table_key(t): t for t in target_tables}

    source_keys = set(source_map.keys())
    target_keys = set(target_map.keys())

    added = [_build_table_info(source_map[k]) for k in sorted(source_keys - target_keys)]
    removed = [_build_table_info(target_map[k]) for k in sorted(target_keys - source_keys)]

    modified: list[TableModification] = []
    for key in sorted(source_keys & target_keys):
        mod = _diff_single_table(source_map[key], target_map[key])
        if mod:
            modified.append(mod)

    return TableDiff(added_tables=added, removed_tables=removed, modified_tables=modified)


def _diff_single_table(source: dict[str, Any], target: dict[str, Any]) -> TableModification | None:
    """Compare columns of a single table.

    Returns None if no differences found.
    """
    source_cols = {c.get("COLUMN_NAME", ""): c for c in source.get("columns", [])}
    target_cols = {c.get("COLUMN_NAME", ""): c for c in target.get("columns", [])}

    src_names = set(source_cols.keys())
    tgt_names = set(target_cols.keys())

    added = [_build_column(source_cols[n]) for n in sorted(src_names - tgt_names)]
    removed = [_build_column(target_cols[n]) for n in sorted(tgt_names - src_names)]

    modified: list[ColumnModification] = []
    for name in sorted(src_names & tgt_names):
        mods = _diff_column(source_cols[name], target_cols[name])
        modified.extend(mods)

    if not added and not removed and not modified:
        return None

    return TableModification(
        table_name=source.get("TABLE_NAME", ""),
        table_schema=source.get("TABLE_SCHEMA", ""),
        added_columns=added,
        removed_columns=removed,
        modified_columns=modified,
    )


def _diff_column(source: dict[str, Any], target: dict[str, Any]) -> list[ColumnModification]:
    """Compare a single column between source and target."""
    mods: list[ColumnModification] = []
    col_name = source.get("COLUMN_NAME", "")

    # Type change
    src_type = source.get("DATA_TYPE", "").lower()
    tgt_type = target.get("DATA_TYPE", "").lower()
    if src_type != tgt_type:
        mods.append(
            ColumnModification(
                column_name=col_name,
                change_type="type_change",
                old_value=tgt_type,
                new_value=src_type,
                is_breaking=True,
            )
        )

    # Length change
    src_len = source.get("CHARACTER_MAXIMUM_LENGTH")
    tgt_len = target.get("CHARACTER_MAXIMUM_LENGTH")
    if src_len != tgt_len and (src_len is not None or tgt_len is not None):
        is_shrink = (src_len or 0) < (tgt_len or 0)
        mods.append(
            ColumnModification(
                column_name=col_name,
                change_type="length_change",
                old_value=str(tgt_len),
                new_value=str(src_len),
                is_breaking=is_shrink,
            )
        )

    # Nullability change
    src_nullable = source.get("IS_NULLABLE", "YES")
    tgt_nullable = target.get("IS_NULLABLE", "YES")
    if src_nullable != tgt_nullable:
        # Becoming NOT NULL is breaking if NULLs exist
        is_breaking = src_nullable == "NO" and tgt_nullable == "YES"
        mods.append(
            ColumnModification(
                column_name=col_name,
                change_type="nullability_change",
                old_value=tgt_nullable,
                new_value=src_nullable,
                is_breaking=is_breaking,
            )
        )

    # Default change
    src_default = source.get("COLUMN_DEFAULT") or ""
    tgt_default = target.get("COLUMN_DEFAULT") or ""
    if src_default != tgt_default:
        mods.append(
            ColumnModification(
                column_name=col_name,
                change_type="default_change",
                old_value=tgt_default,
                new_value=src_default,
                is_breaking=False,
            )
        )

    return mods


def diff_foreign_keys(
    source_fks: list[dict[str, Any]],
    target_fks: list[dict[str, Any]],
) -> tuple[list[ForeignKeyInfo], list[ForeignKeyInfo]]:
    """Compare foreign keys between source and target.

    Returns:
        Tuple of (added, removed) foreign keys.
    """
    source_map = {_fk_key(fk): fk for fk in source_fks}
    target_map = {_fk_key(fk): fk for fk in target_fks}

    src_keys = set(source_map.keys())
    tgt_keys = set(target_map.keys())

    added = [_fk_to_info(source_map[k]) for k in sorted(src_keys - tgt_keys)]
    removed = [_fk_to_info(target_map[k]) for k in sorted(tgt_keys - src_keys)]

    return added, removed


def _fk_to_info(fk: dict[str, Any]) -> ForeignKeyInfo:
    """Convert raw FK dict to ForeignKeyInfo."""
    return ForeignKeyInfo(
        constraint_name=fk.get("constraint_name", ""),
        parent_schema=fk.get("parent_schema", ""),
        parent_table=fk.get("parent_table", ""),
        parent_column=fk.get("parent_column", ""),
        referenced_schema=fk.get("referenced_schema", ""),
        referenced_table=fk.get("referenced_table", ""),
        referenced_column=fk.get("referenced_column", ""),
    )
