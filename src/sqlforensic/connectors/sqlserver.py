"""SQL Server database connector using pyodbc."""

from __future__ import annotations

import logging
from typing import Any

from sqlforensic.config import ConnectionConfig
from sqlforensic.connectors.base import BaseConnector

logger = logging.getLogger(__name__)


class SQLServerConnector(BaseConnector):
    """Connector for Microsoft SQL Server databases.

    Uses pyodbc for database connectivity. All operations are read-only.
    """

    def __init__(self, config: ConnectionConfig) -> None:
        super().__init__(config)

    def _build_connection_string(self) -> str:
        """Build ODBC connection string from config."""
        if self.config.connection_string:
            return self.config.connection_string

        parts = [
            "DRIVER={ODBC Driver 17 for SQL Server}",
            f"SERVER={self.config.server},{self.config.port}",
            f"DATABASE={self.config.database}",
        ]

        if self.config.trusted_connection:
            parts.append("Trusted_Connection=Yes")
        else:
            parts.append(f"UID={self.config.username}")
            parts.append(f"PWD={self.config.password}")

        if self.config.ssl:
            parts.append("Encrypt=Yes")
            parts.append("TrustServerCertificate=No")

        return ";".join(parts)

    def connect(self) -> None:
        """Establish connection to SQL Server."""
        import pyodbc

        conn_str = self._build_connection_string()
        logger.info("Connecting to SQL Server: %s", self.config.get_masked_connection_info())
        self._connection = pyodbc.connect(conn_str, readonly=True)
        logger.info("Connected successfully")

    def disconnect(self) -> None:
        """Close SQL Server connection."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None
            logger.info("Disconnected from SQL Server")

    def execute_query(
        self, query: str, params: tuple[Any, ...] | None = None
    ) -> list[dict[str, Any]]:
        """Execute a read-only query and return results as list of dicts."""
        if self._connection is None:
            raise ConnectionError("Not connected to database")

        cursor = self._connection.cursor()
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]
        finally:
            cursor.close()

    def get_tables(self) -> list[dict[str, Any]]:
        """Retrieve all user tables with row counts."""
        query = """
            SELECT t.TABLE_SCHEMA, t.TABLE_NAME,
                   (SELECT SUM(p.rows) FROM sys.partitions p
                    JOIN sys.tables st ON p.object_id = st.object_id
                    JOIN sys.schemas ss ON st.schema_id = ss.schema_id
                    WHERE st.name = t.TABLE_NAME
                      AND ss.name = t.TABLE_SCHEMA
                      AND p.index_id IN (0, 1)) AS row_count
            FROM INFORMATION_SCHEMA.TABLES t
            WHERE t.TABLE_TYPE = 'BASE TABLE'
            ORDER BY t.TABLE_SCHEMA, t.TABLE_NAME
        """
        return self.execute_query(query)

    def get_columns(self, table_schema: str, table_name: str) -> list[dict[str, Any]]:
        """Retrieve columns for a specific table."""
        query = """
            SELECT c.COLUMN_NAME, c.DATA_TYPE, c.CHARACTER_MAXIMUM_LENGTH,
                   c.IS_NULLABLE, c.COLUMN_DEFAULT, c.ORDINAL_POSITION,
                   CASE WHEN pk.COLUMN_NAME IS NOT NULL THEN 1 ELSE 0 END AS is_primary_key
            FROM INFORMATION_SCHEMA.COLUMNS c
            LEFT JOIN (
                SELECT ku.TABLE_SCHEMA, ku.TABLE_NAME, ku.COLUMN_NAME
                FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ku
                    ON tc.CONSTRAINT_NAME = ku.CONSTRAINT_NAME
                WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
            ) pk ON c.TABLE_SCHEMA = pk.TABLE_SCHEMA
                 AND c.TABLE_NAME = pk.TABLE_NAME
                 AND c.COLUMN_NAME = pk.COLUMN_NAME
            WHERE c.TABLE_SCHEMA = ? AND c.TABLE_NAME = ?
            ORDER BY c.ORDINAL_POSITION
        """
        return self.execute_query(query, (table_schema, table_name))

    def get_foreign_keys(self) -> list[dict[str, Any]]:
        """Retrieve all foreign key relationships."""
        query = """
            SELECT fk.name AS constraint_name,
                   SCHEMA_NAME(tp.schema_id) AS parent_schema,
                   tp.name AS parent_table,
                   cp.name AS parent_column,
                   SCHEMA_NAME(tr.schema_id) AS referenced_schema,
                   tr.name AS referenced_table,
                   cr.name AS referenced_column
            FROM sys.foreign_keys fk
            JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
            JOIN sys.tables tp ON fkc.parent_object_id = tp.object_id
            JOIN sys.columns cp ON fkc.parent_object_id = cp.object_id
                 AND fkc.parent_column_id = cp.column_id
            JOIN sys.tables tr ON fkc.referenced_object_id = tr.object_id
            JOIN sys.columns cr ON fkc.referenced_object_id = cr.object_id
                 AND fkc.referenced_column_id = cr.column_id
            ORDER BY tp.name, fk.name
        """
        return self.execute_query(query)

    def get_stored_procedures(self) -> list[dict[str, Any]]:
        """Retrieve all stored procedures with their definitions."""
        query = """
            SELECT ROUTINE_SCHEMA, ROUTINE_NAME, ROUTINE_DEFINITION,
                   CREATED, LAST_ALTERED
            FROM INFORMATION_SCHEMA.ROUTINES
            WHERE ROUTINE_TYPE = 'PROCEDURE'
              AND ROUTINE_SCHEMA NOT IN ('sys')
            ORDER BY ROUTINE_SCHEMA, ROUTINE_NAME
        """
        return self.execute_query(query)

    def get_views(self) -> list[dict[str, Any]]:
        """Retrieve all views with definitions."""
        query = """
            SELECT TABLE_SCHEMA, TABLE_NAME, VIEW_DEFINITION
            FROM INFORMATION_SCHEMA.VIEWS
            WHERE TABLE_SCHEMA NOT IN ('sys', 'INFORMATION_SCHEMA')
            ORDER BY TABLE_SCHEMA, TABLE_NAME
        """
        return self.execute_query(query)

    def get_functions(self) -> list[dict[str, Any]]:
        """Retrieve all user-defined functions."""
        query = """
            SELECT ROUTINE_SCHEMA, ROUTINE_NAME, ROUTINE_DEFINITION,
                   DATA_TYPE, CREATED, LAST_ALTERED
            FROM INFORMATION_SCHEMA.ROUTINES
            WHERE ROUTINE_TYPE = 'FUNCTION'
              AND ROUTINE_SCHEMA NOT IN ('sys')
            ORDER BY ROUTINE_SCHEMA, ROUTINE_NAME
        """
        return self.execute_query(query)

    def get_indexes(self) -> list[dict[str, Any]]:
        """Retrieve all indexes with usage statistics."""
        query = """
            SELECT SCHEMA_NAME(t.schema_id) AS table_schema,
                   t.name AS table_name,
                   i.name AS index_name,
                   i.type_desc AS index_type,
                   i.is_unique,
                   i.is_primary_key,
                   STUFF((
                       SELECT ', ' + c.name
                       FROM sys.index_columns ic
                       JOIN sys.columns c ON ic.object_id = c.object_id
                            AND ic.column_id = c.column_id
                       WHERE ic.object_id = i.object_id AND ic.index_id = i.index_id
                       ORDER BY ic.key_ordinal
                       FOR XML PATH('')
                   ), 1, 2, '') AS columns,
                   ius.user_seeks, ius.user_scans, ius.user_lookups, ius.user_updates
            FROM sys.indexes i
            JOIN sys.tables t ON i.object_id = t.object_id
            LEFT JOIN sys.dm_db_index_usage_stats ius
                ON i.object_id = ius.object_id AND i.index_id = ius.index_id
            WHERE i.name IS NOT NULL
              AND OBJECTPROPERTY(i.object_id, 'IsUserTable') = 1
            ORDER BY t.name, i.name
        """
        return self.execute_query(query)

    def get_missing_indexes(self) -> list[dict[str, Any]]:
        """Retrieve missing index recommendations from SQL Server DMVs."""
        query = """
            SELECT d.statement AS table_name,
                   d.equality_columns, d.inequality_columns, d.included_columns,
                   s.avg_total_user_cost * s.avg_user_impact *
                   (s.user_seeks + s.user_scans) AS improvement_measure,
                   s.user_seeks, s.user_scans
            FROM sys.dm_db_missing_index_details d
            JOIN sys.dm_db_missing_index_groups g ON d.index_handle = g.index_handle
            JOIN sys.dm_db_missing_index_group_stats s
                ON g.index_group_handle = s.group_handle
            WHERE d.database_id = DB_ID()
            ORDER BY improvement_measure DESC
        """
        return self.execute_query(query)

    def get_table_sizes(self) -> list[dict[str, Any]]:
        """Retrieve table sizes and row counts."""
        query = """
            SELECT s.name AS table_schema,
                   t.name AS table_name,
                   SUM(p.rows) AS row_count,
                   SUM(a.total_pages) * 8 AS total_space_kb,
                   SUM(a.used_pages) * 8 AS used_space_kb
            FROM sys.tables t
            JOIN sys.schemas s ON t.schema_id = s.schema_id
            JOIN sys.indexes i ON t.object_id = i.object_id
            JOIN sys.partitions p ON i.object_id = p.object_id AND i.index_id = p.index_id
            JOIN sys.allocation_units a ON p.partition_id = a.container_id
            WHERE t.is_ms_shipped = 0 AND i.index_id <= 1
            GROUP BY s.name, t.name
            ORDER BY SUM(a.total_pages) DESC
        """
        return self.execute_query(query)

    def get_permissions(self) -> list[dict[str, Any]]:
        """Retrieve database permissions for security analysis."""
        query = """
            SELECT pr.name AS principal_name, pr.type_desc AS principal_type,
                   pe.permission_name, pe.state_desc AS permission_state,
                   OBJECT_NAME(pe.major_id) AS object_name,
                   pe.class_desc
            FROM sys.database_permissions pe
            JOIN sys.database_principals pr ON pe.grantee_principal_id = pr.principal_id
            WHERE pr.name NOT IN ('public', 'guest', 'dbo')
            ORDER BY pr.name, pe.permission_name
        """
        return self.execute_query(query)
