"""Stored procedure, view, and function diff logic."""

from __future__ import annotations

from typing import Any

from sqlforensic.diff.diff_result import ObjectDiff, ObjectModification, hash_body


def _object_key(obj: dict[str, Any], name_field: str, schema_field: str) -> str:
    """Build a lookup key for a database object."""
    schema = obj.get(schema_field, "")
    name = obj.get(name_field, "")
    return f"{schema}.{name}"


def diff_procedures(
    source_sps: list[dict[str, Any]],
    target_sps: list[dict[str, Any]],
) -> ObjectDiff:
    """Compare stored procedures between source and target."""
    return _diff_objects(
        source_sps,
        target_sps,
        name_field="ROUTINE_NAME",
        schema_field="ROUTINE_SCHEMA",
        body_field="ROUTINE_DEFINITION",
        object_type="procedure",
    )


def diff_views(
    source_views: list[dict[str, Any]],
    target_views: list[dict[str, Any]],
) -> ObjectDiff:
    """Compare views between source and target."""
    return _diff_objects(
        source_views,
        target_views,
        name_field="TABLE_NAME",
        schema_field="TABLE_SCHEMA",
        body_field="VIEW_DEFINITION",
        object_type="view",
    )


def diff_functions(
    source_funcs: list[dict[str, Any]],
    target_funcs: list[dict[str, Any]],
) -> ObjectDiff:
    """Compare functions between source and target."""
    return _diff_objects(
        source_funcs,
        target_funcs,
        name_field="ROUTINE_NAME",
        schema_field="ROUTINE_SCHEMA",
        body_field="ROUTINE_DEFINITION",
        object_type="function",
    )


def _diff_objects(
    source: list[dict[str, Any]],
    target: list[dict[str, Any]],
    name_field: str,
    schema_field: str,
    body_field: str,
    object_type: str,
) -> ObjectDiff:
    """Generic diff for named database objects with a body."""
    source_map = {_object_key(o, name_field, schema_field): o for o in source}
    target_map = {_object_key(o, name_field, schema_field): o for o in target}

    src_keys = set(source_map.keys())
    tgt_keys = set(target_map.keys())

    added = [
        {"schema": source_map[k].get(schema_field, ""), "name": source_map[k].get(name_field, "")}
        for k in sorted(src_keys - tgt_keys)
    ]
    removed = [
        {"schema": target_map[k].get(schema_field, ""), "name": target_map[k].get(name_field, "")}
        for k in sorted(tgt_keys - src_keys)
    ]

    modified: list[ObjectModification] = []
    for key in sorted(src_keys & tgt_keys):
        src_hash = hash_body(source_map[key].get(body_field))
        tgt_hash = hash_body(target_map[key].get(body_field))
        if src_hash != tgt_hash:
            modified.append(
                ObjectModification(
                    name=source_map[key].get(name_field, ""),
                    schema=source_map[key].get(schema_field, ""),
                    object_type=object_type,
                    source_hash=src_hash,
                    target_hash=tgt_hash,
                )
            )

    return ObjectDiff(added=added, removed=removed, modified=modified)
