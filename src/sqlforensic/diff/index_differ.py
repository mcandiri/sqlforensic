"""Index diff logic."""

from __future__ import annotations

from typing import Any

from sqlforensic.diff.diff_result import IndexDiff, IndexInfo, IndexModification


def _index_key(idx: dict[str, Any]) -> str:
    """Build a lookup key for an index."""
    schema = idx.get("table_schema", "")
    table = idx.get("table_name", "")
    name = idx.get("index_name", "")
    return f"{schema}.{table}.{name}"


def _to_index_info(idx: dict[str, Any]) -> IndexInfo:
    """Convert raw index dict to IndexInfo."""
    return IndexInfo(
        table_schema=idx.get("table_schema", ""),
        table_name=idx.get("table_name", ""),
        index_name=idx.get("index_name", ""),
        index_type=idx.get("index_type", ""),
        is_unique=bool(idx.get("is_unique")),
        is_primary_key=bool(idx.get("is_primary_key")),
        columns=str(idx.get("columns", "")),
    )


def diff_indexes(
    source_indexes: list[dict[str, Any]],
    target_indexes: list[dict[str, Any]],
) -> IndexDiff:
    """Compare indexes between source and target.

    Args:
        source_indexes: Indexes from the source schema.
        target_indexes: Indexes from the target schema.

    Returns:
        IndexDiff with added, removed, and modified indexes.
    """
    source_map = {_index_key(i): i for i in source_indexes}
    target_map = {_index_key(i): i for i in target_indexes}

    src_keys = set(source_map.keys())
    tgt_keys = set(target_map.keys())

    added = [_to_index_info(source_map[k]) for k in sorted(src_keys - tgt_keys)]
    removed = [_to_index_info(target_map[k]) for k in sorted(tgt_keys - src_keys)]

    modified: list[IndexModification] = []
    for key in sorted(src_keys & tgt_keys):
        src_cols = str(source_map[key].get("columns", ""))
        tgt_cols = str(target_map[key].get("columns", ""))
        if src_cols != tgt_cols:
            modified.append(
                IndexModification(
                    table_name=source_map[key].get("table_name", ""),
                    index_name=source_map[key].get("index_name", ""),
                    old_columns=tgt_cols,
                    new_columns=src_cols,
                )
            )

    return IndexDiff(
        added_indexes=added,
        removed_indexes=removed,
        modified_indexes=modified,
    )
