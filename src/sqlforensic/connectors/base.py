"""Abstract base connector for database connections."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from sqlforensic.config import ConnectionConfig

logger = logging.getLogger(__name__)


class BaseConnector(ABC):
    """Abstract base class for database connectors.

    All connectors are strictly read-only. They never execute DDL or DML
    statements that modify the database.
    """

    def __init__(self, config: ConnectionConfig) -> None:
        self.config = config
        self._connection: Any = None

    @abstractmethod
    def connect(self) -> None:
        """Establish a connection to the database."""

    @abstractmethod
    def disconnect(self) -> None:
        """Close the database connection."""

    @abstractmethod
    def execute_query(
        self, query: str, params: tuple[Any, ...] | None = None
    ) -> list[dict[str, Any]]:
        """Execute a SELECT query and return results as list of dicts."""

    @abstractmethod
    def get_tables(self) -> list[dict[str, Any]]:
        """Retrieve all tables with metadata."""

    @abstractmethod
    def get_columns(self, table_schema: str, table_name: str) -> list[dict[str, Any]]:
        """Retrieve columns for a specific table."""

    @abstractmethod
    def get_foreign_keys(self) -> list[dict[str, Any]]:
        """Retrieve all foreign key relationships."""

    @abstractmethod
    def get_stored_procedures(self) -> list[dict[str, Any]]:
        """Retrieve all stored procedures with their bodies."""

    @abstractmethod
    def get_views(self) -> list[dict[str, Any]]:
        """Retrieve all views with their definitions."""

    @abstractmethod
    def get_functions(self) -> list[dict[str, Any]]:
        """Retrieve all user-defined functions."""

    @abstractmethod
    def get_indexes(self) -> list[dict[str, Any]]:
        """Retrieve all indexes with usage statistics."""

    @abstractmethod
    def get_missing_indexes(self) -> list[dict[str, Any]]:
        """Retrieve missing index recommendations."""

    @abstractmethod
    def get_table_sizes(self) -> list[dict[str, Any]]:
        """Retrieve table size and row count information."""

    @abstractmethod
    def get_permissions(self) -> list[dict[str, Any]]:
        """Retrieve database permissions for security analysis."""

    @property
    def is_connected(self) -> bool:
        """Check if the connector has an active connection."""
        return self._connection is not None

    def __enter__(self) -> BaseConnector:
        self.connect()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.disconnect()
