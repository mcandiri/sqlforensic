"""PostgreSQL database connector using psycopg2."""

from __future__ import annotations

import logging
from typing import Any

from sqlforensic.config import ConnectionConfig
from sqlforensic.connectors.base import BaseConnector

logger = logging.getLogger(__name__)


class PostgreSQLConnector(BaseConnector):
    """Connector for PostgreSQL databases.

    Uses psycopg2 for database connectivity. All operations are read-only.
    """

    def __init__(self, config: ConnectionConfig) -> None:
        super().__init__(config)

    def connect(self) -> None:
        """Establish connection to PostgreSQL."""
        import psycopg2
        import psycopg2.extras

        if self.config.connection_string:
            logger.info("Connecting to PostgreSQL via connection string")
            self._connection = psycopg2.connect(self.config.connection_string)
        else:
            logger.info("Connecting to PostgreSQL: %s", self.config.get_masked_connection_info())
            kwargs: dict[str, Any] = {
                "host": self.config.server,
                "port": self.config.port,
                "dbname": self.config.database,
                "user": self.config.username,
                "password": self.config.password,
            }
            if self.config.ssl:
                kwargs["sslmode"] = "require"
            self._connection = psycopg2.connect(**kwargs)

        self._connection.set_session(readonly=True, autocommit=True)
        logger.info("Connected successfully")

    def disconnect(self) -> None:
        """Close PostgreSQL connection."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None
            logger.info("Disconnected from PostgreSQL")

    def execute_query(
        self, query: str, params: tuple[Any, ...] | None = None
    ) -> list[dict[str, Any]]:
        """Execute a read-only query and return results as list of dicts."""
        if self._connection is None:
            raise ConnectionError("Not connected to database")

        import psycopg2.extras

        cursor = self._connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            if cursor.description is None:
                return []
            return [dict(row) for row in cursor.fetchall()]
        finally:
            cursor.close()

    def get_tables(self) -> list[dict[str, Any]]:
        """Retrieve all user tables with row counts."""
        query = """
            SELECT t.table_schema AS "TABLE_SCHEMA",
                   t.table_name AS "TABLE_NAME",
                   s.n_live_tup AS row_count
            FROM information_schema.tables t
            LEFT JOIN pg_stat_user_tables s
                ON t.table_schema = s.schemaname AND t.table_name = s.relname
            WHERE t.table_type = 'BASE TABLE'
              AND t.table_schema NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
            ORDER BY t.table_schema, t.table_name
        """
        return self.execute_query(query)

    def get_columns(self, table_schema: str, table_name: str) -> list[dict[str, Any]]:
        """Retrieve columns for a specific table."""
        query = """
            SELECT c.column_name AS "COLUMN_NAME",
                   c.data_type AS "DATA_TYPE",
                   c.character_maximum_length AS "CHARACTER_MAXIMUM_LENGTH",
                   c.is_nullable AS "IS_NULLABLE",
                   c.column_default AS "COLUMN_DEFAULT",
                   c.ordinal_position AS "ORDINAL_POSITION",
                   CASE WHEN pk.column_name IS NOT NULL THEN 1 ELSE 0 END AS is_primary_key
            FROM information_schema.columns c
            LEFT JOIN (
                SELECT kcu.table_schema, kcu.table_name, kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY'
            ) pk ON c.table_schema = pk.table_schema
                 AND c.table_name = pk.table_name
                 AND c.column_name = pk.column_name
            WHERE c.table_schema = %s AND c.table_name = %s
            ORDER BY c.ordinal_position
        """
        return self.execute_query(query, (table_schema, table_name))

    def get_foreign_keys(self) -> list[dict[str, Any]]:
        """Retrieve all foreign key relationships."""
        query = """
            SELECT tc.constraint_name,
                   tc.table_schema AS parent_schema,
                   tc.table_name AS parent_table,
                   kcu.column_name AS parent_column,
                   ccu.table_schema AS referenced_schema,
                   ccu.table_name AS referenced_table,
                   ccu.column_name AS referenced_column
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
            ORDER BY tc.table_name, tc.constraint_name
        """
        return self.execute_query(query)

    def get_stored_procedures(self) -> list[dict[str, Any]]:
        """Retrieve all stored procedures (functions in PostgreSQL)."""
        query = """
            SELECT n.nspname AS "ROUTINE_SCHEMA",
                   p.proname AS "ROUTINE_NAME",
                   pg_get_functiondef(p.oid) AS "ROUTINE_DEFINITION",
                   NULL AS "CREATED",
                   NULL AS "LAST_ALTERED"
            FROM pg_proc p
            JOIN pg_namespace n ON p.pronamespace = n.oid
            WHERE n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
              AND p.prokind = 'p'
            ORDER BY n.nspname, p.proname
        """
        return self.execute_query(query)

    def get_views(self) -> list[dict[str, Any]]:
        """Retrieve all views with definitions."""
        query = """
            SELECT table_schema AS "TABLE_SCHEMA",
                   table_name AS "TABLE_NAME",
                   view_definition AS "VIEW_DEFINITION"
            FROM information_schema.views
            WHERE table_schema NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
            ORDER BY table_schema, table_name
        """
        return self.execute_query(query)

    def get_functions(self) -> list[dict[str, Any]]:
        """Retrieve all user-defined functions."""
        query = """
            SELECT n.nspname AS "ROUTINE_SCHEMA",
                   p.proname AS "ROUTINE_NAME",
                   pg_get_functiondef(p.oid) AS "ROUTINE_DEFINITION",
                   pg_catalog.pg_get_function_result(p.oid) AS "DATA_TYPE",
                   NULL AS "CREATED",
                   NULL AS "LAST_ALTERED"
            FROM pg_proc p
            JOIN pg_namespace n ON p.pronamespace = n.oid
            WHERE n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
              AND p.prokind = 'f'
            ORDER BY n.nspname, p.proname
        """
        return self.execute_query(query)

    def get_indexes(self) -> list[dict[str, Any]]:
        """Retrieve all indexes with usage statistics."""
        query = """
            SELECT schemaname AS table_schema,
                   tablename AS table_name,
                   indexname AS index_name,
                   CASE WHEN indexdef LIKE '%%UNIQUE%%' THEN 1 ELSE 0 END AS is_unique,
                   indexdef AS index_definition,
                   idx_scan AS user_seeks,
                   idx_tup_read AS user_scans,
                   0 AS user_lookups,
                   idx_tup_fetch AS user_fetches
            FROM pg_indexes
            LEFT JOIN pg_stat_user_indexes psi
                ON pg_indexes.indexname = psi.indexrelname
                AND pg_indexes.schemaname = psi.schemaname
            WHERE pg_indexes.schemaname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
            ORDER BY tablename, indexname
        """
        return self.execute_query(query)

    def get_missing_indexes(self) -> list[dict[str, Any]]:
        """Retrieve tables that may benefit from additional indexes.

        PostgreSQL doesn't have a direct DMV like SQL Server, so we identify
        tables with sequential scans that could benefit from indexes.
        """
        query = """
            SELECT schemaname || '.' || relname AS table_name,
                   seq_scan,
                   seq_tup_read,
                   idx_scan,
                   seq_tup_read::float / NULLIF(seq_scan, 0) AS avg_rows_per_scan,
                   n_live_tup AS row_count
            FROM pg_stat_user_tables
            WHERE seq_scan > 0
              AND n_live_tup > 1000
              AND (idx_scan IS NULL OR seq_scan > idx_scan * 2)
            ORDER BY seq_tup_read DESC
            LIMIT 50
        """
        return self.execute_query(query)

    def get_table_sizes(self) -> list[dict[str, Any]]:
        """Retrieve table sizes and row counts."""
        query = """
            SELECT n.nspname AS table_schema,
                   c.relname AS table_name,
                   c.reltuples::bigint AS row_count,
                   pg_total_relation_size(c.oid) / 1024 AS total_space_kb,
                   pg_relation_size(c.oid) / 1024 AS used_space_kb
            FROM pg_class c
            JOIN pg_namespace n ON c.relnamespace = n.oid
            WHERE c.relkind = 'r'
              AND n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
            ORDER BY pg_total_relation_size(c.oid) DESC
        """
        return self.execute_query(query)

    def get_permissions(self) -> list[dict[str, Any]]:
        """Retrieve database permissions for security analysis."""
        query = """
            SELECT grantee AS principal_name,
                   'ROLE' AS principal_type,
                   privilege_type AS permission_name,
                   is_grantable AS permission_state,
                   table_schema || '.' || table_name AS object_name,
                   table_schema AS class_desc
            FROM information_schema.role_table_grants
            WHERE grantee NOT IN ('postgres', 'PUBLIC')
              AND table_schema NOT IN ('pg_catalog', 'information_schema')
            ORDER BY grantee, privilege_type
        """
        return self.execute_query(query)
