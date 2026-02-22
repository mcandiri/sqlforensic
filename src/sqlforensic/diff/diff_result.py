"""Data classes for schema diff results."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


@dataclass
class ColumnInfo:
    """Column metadata."""

    name: str = ""
    data_type: str = ""
    max_length: int | None = None
    is_nullable: bool = True
    default: str | None = None
    ordinal: int = 0
    is_primary_key: bool = False


@dataclass
class ColumnModification:
    """A single column change between source and target."""

    column_name: str = ""
    change_type: str = ""  # type_change, nullability_change, default_change, length_change
    old_value: str = ""
    new_value: str = ""
    is_breaking: bool = False
    affected_rows_estimate: int | None = None


@dataclass
class ConstraintInfo:
    """Constraint metadata (PK, unique, check)."""

    name: str = ""
    constraint_type: str = ""  # PRIMARY KEY, UNIQUE, CHECK
    columns: list[str] = field(default_factory=list)


@dataclass
class ForeignKeyInfo:
    """Foreign key metadata."""

    constraint_name: str = ""
    parent_schema: str = ""
    parent_table: str = ""
    parent_column: str = ""
    referenced_schema: str = ""
    referenced_table: str = ""
    referenced_column: str = ""


@dataclass
class TableInfo:
    """Table metadata for added/removed tables."""

    schema: str = ""
    name: str = ""
    columns: list[ColumnInfo] = field(default_factory=list)
    row_count: int = 0


@dataclass
class TableModification:
    """All changes to a single table between source and target."""

    table_name: str = ""
    table_schema: str = ""
    added_columns: list[ColumnInfo] = field(default_factory=list)
    removed_columns: list[ColumnInfo] = field(default_factory=list)
    modified_columns: list[ColumnModification] = field(default_factory=list)
    added_constraints: list[ConstraintInfo] = field(default_factory=list)
    removed_constraints: list[ConstraintInfo] = field(default_factory=list)
    added_foreign_keys: list[ForeignKeyInfo] = field(default_factory=list)
    removed_foreign_keys: list[ForeignKeyInfo] = field(default_factory=list)
    risk_score: float = 0.0
    risk_details: list[str] = field(default_factory=list)


@dataclass
class TableDiff:
    """Table-level diff between source and target."""

    added_tables: list[TableInfo] = field(default_factory=list)
    removed_tables: list[TableInfo] = field(default_factory=list)
    modified_tables: list[TableModification] = field(default_factory=list)


@dataclass
class IndexInfo:
    """Index metadata."""

    table_schema: str = ""
    table_name: str = ""
    index_name: str = ""
    index_type: str = ""
    is_unique: bool = False
    is_primary_key: bool = False
    columns: str = ""


@dataclass
class IndexModification:
    """Index change — same name but different columns."""

    table_name: str = ""
    index_name: str = ""
    old_columns: str = ""
    new_columns: str = ""


@dataclass
class IndexDiff:
    """Index-level diff between source and target."""

    added_indexes: list[IndexInfo] = field(default_factory=list)
    removed_indexes: list[IndexInfo] = field(default_factory=list)
    modified_indexes: list[IndexModification] = field(default_factory=list)


@dataclass
class ObjectModification:
    """SP/View/Function change."""

    name: str = ""
    schema: str = ""
    object_type: str = ""  # procedure, view, function
    source_hash: str = ""
    target_hash: str = ""


@dataclass
class ObjectDiff:
    """SP/View/Function diff between source and target."""

    added: list[dict[str, str]] = field(default_factory=list)
    removed: list[dict[str, str]] = field(default_factory=list)
    modified: list[ObjectModification] = field(default_factory=list)


@dataclass
class RiskAssessment:
    """Risk assessment for a single change."""

    change_description: str = ""
    table: str = ""
    risk_score: float = 0.0
    risk_level: str = "NONE"  # NONE, LOW, MEDIUM, HIGH, CRITICAL
    affected_objects: list[str] = field(default_factory=list)
    breaking_changes: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


@dataclass
class DiffResult:
    """Complete schema diff result."""

    source_database: str = ""
    target_database: str = ""
    source_server: str = ""
    target_server: str = ""
    provider: str = ""
    tables: TableDiff = field(default_factory=TableDiff)
    indexes: IndexDiff = field(default_factory=IndexDiff)
    procedures: ObjectDiff = field(default_factory=ObjectDiff)
    views: ObjectDiff = field(default_factory=ObjectDiff)
    functions: ObjectDiff = field(default_factory=ObjectDiff)
    foreign_keys_added: list[ForeignKeyInfo] = field(default_factory=list)
    foreign_keys_removed: list[ForeignKeyInfo] = field(default_factory=list)
    risks: list[RiskAssessment] = field(default_factory=list)
    risk_level: str = "NONE"
    include_data: bool = False
    row_count_changes: list[dict[str, int | str]] = field(default_factory=list)

    @property
    def total_changes(self) -> int:
        """Total number of changes across all categories."""
        return (
            len(self.tables.added_tables)
            + len(self.tables.removed_tables)
            + len(self.tables.modified_tables)
            + len(self.indexes.added_indexes)
            + len(self.indexes.removed_indexes)
            + len(self.indexes.modified_indexes)
            + len(self.procedures.added)
            + len(self.procedures.removed)
            + len(self.procedures.modified)
            + len(self.views.added)
            + len(self.views.removed)
            + len(self.views.modified)
            + len(self.functions.added)
            + len(self.functions.removed)
            + len(self.functions.modified)
            + len(self.foreign_keys_added)
            + len(self.foreign_keys_removed)
        )

    @property
    def has_changes(self) -> bool:
        """Whether any differences were found."""
        return self.total_changes > 0

    @property
    def summary(self) -> dict[str, dict[str, int]]:
        """Summary counts by category."""
        return {
            "Tables": {
                "Added": len(self.tables.added_tables),
                "Removed": len(self.tables.removed_tables),
                "Modified": len(self.tables.modified_tables),
            },
            "Columns": {
                "Added": sum(len(t.added_columns) for t in self.tables.modified_tables),
                "Removed": sum(len(t.removed_columns) for t in self.tables.modified_tables),
                "Modified": sum(len(t.modified_columns) for t in self.tables.modified_tables),
            },
            "Indexes": {
                "Added": len(self.indexes.added_indexes),
                "Removed": len(self.indexes.removed_indexes),
                "Modified": len(self.indexes.modified_indexes),
            },
            "Foreign Keys": {
                "Added": len(self.foreign_keys_added),
                "Removed": len(self.foreign_keys_removed),
                "Modified": 0,
            },
            "Stored Procedures": {
                "Added": len(self.procedures.added),
                "Removed": len(self.procedures.removed),
                "Modified": len(self.procedures.modified),
            },
            "Views": {
                "Added": len(self.views.added),
                "Removed": len(self.views.removed),
                "Modified": len(self.views.modified),
            },
            "Functions": {
                "Added": len(self.functions.added),
                "Removed": len(self.functions.removed),
                "Modified": len(self.functions.modified),
            },
        }


def hash_body(body: str | None) -> str:
    """Hash a SQL body for comparison."""
    if not body:
        return ""
    normalized = " ".join(body.strip().split()).lower()
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]
