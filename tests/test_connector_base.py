"""Tests for BaseConnector abstract class and context manager protocol."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from sqlforensic.config import ConnectionConfig
from sqlforensic.connectors.base import BaseConnector


class ConcreteConnector(BaseConnector):
    """Minimal concrete implementation for testing the base class."""

    def connect(self) -> None:
        self._connection = "active"

    def disconnect(self) -> None:
        self._connection = None

    def execute_query(self, query, params=None):  # type: ignore[override]
        return []

    def get_tables(self):  # type: ignore[override]
        return []

    def get_columns(self, table_schema, table_name):  # type: ignore[override]
        return []

    def get_foreign_keys(self):  # type: ignore[override]
        return []

    def get_stored_procedures(self):  # type: ignore[override]
        return []

    def get_views(self):  # type: ignore[override]
        return []

    def get_functions(self):  # type: ignore[override]
        return []

    def get_indexes(self):  # type: ignore[override]
        return []

    def get_missing_indexes(self):  # type: ignore[override]
        return []

    def get_table_sizes(self):  # type: ignore[override]
        return []

    def get_permissions(self):  # type: ignore[override]
        return []


@pytest.fixture
def config() -> ConnectionConfig:
    return ConnectionConfig(
        provider="sqlserver",
        server="localhost",
        database="TestDB",
        username="sa",
        password="secret",
    )


class TestBaseConnector:
    def test_is_connected_false_initially(self, config: ConnectionConfig) -> None:
        conn = ConcreteConnector(config)
        assert conn.is_connected is False

    def test_is_connected_true_after_connect(self, config: ConnectionConfig) -> None:
        conn = ConcreteConnector(config)
        conn.connect()
        assert conn.is_connected is True

    def test_is_connected_false_after_disconnect(self, config: ConnectionConfig) -> None:
        conn = ConcreteConnector(config)
        conn.connect()
        conn.disconnect()
        assert conn.is_connected is False

    def test_context_manager_connects_and_disconnects(self, config: ConnectionConfig) -> None:
        conn = ConcreteConnector(config)
        with conn:
            assert conn.is_connected is True
        assert conn.is_connected is False

    def test_context_manager_disconnects_on_exception(self, config: ConnectionConfig) -> None:
        conn = ConcreteConnector(config)
        with pytest.raises(ValueError):
            with conn:
                assert conn.is_connected is True
                raise ValueError("test error")
        assert conn.is_connected is False

    def test_config_stored(self, config: ConnectionConfig) -> None:
        conn = ConcreteConnector(config)
        assert conn.config.database == "TestDB"
        assert conn.config.provider == "sqlserver"


class TestSQLServerConnector:
    def test_connection_error_wraps_exception(self) -> None:
        """Connection errors should be wrapped in ConnectionError."""
        from sqlforensic.connectors.sqlserver import SQLServerConnector

        config = ConnectionConfig(
            provider="sqlserver",
            server="nonexistent",
            database="TestDB",
            username="sa",
            password="wrong",
        )
        connector = SQLServerConnector(config)

        mock_pyodbc = MagicMock()
        mock_pyodbc.connect.side_effect = Exception("Connection refused")
        mock_pyodbc.Error = Exception
        with patch.dict("sys.modules", {"pyodbc": mock_pyodbc}):
            with pytest.raises(ConnectionError, match="Failed to connect"):
                connector.connect()

    def test_execute_query_without_connection_raises(self) -> None:
        from sqlforensic.connectors.sqlserver import SQLServerConnector

        config = ConnectionConfig(provider="sqlserver", database="DB")
        connector = SQLServerConnector(config)
        with pytest.raises(ConnectionError, match="Not connected"):
            connector.execute_query("SELECT 1")

    def test_build_connection_string_trusted(self) -> None:
        from sqlforensic.connectors.sqlserver import SQLServerConnector

        config = ConnectionConfig(
            provider="sqlserver",
            server="myhost",
            database="MyDB",
            port=1433,
            trusted_connection=True,
        )
        connector = SQLServerConnector(config)
        conn_str = connector._build_connection_string()
        assert "Trusted_Connection=Yes" in conn_str
        assert "UID=" not in conn_str

    def test_build_connection_string_ssl(self) -> None:
        from sqlforensic.connectors.sqlserver import SQLServerConnector

        config = ConnectionConfig(
            provider="sqlserver",
            server="myhost",
            database="MyDB",
            username="sa",
            password="pw",
            port=1433,
            ssl=True,
        )
        connector = SQLServerConnector(config)
        conn_str = connector._build_connection_string()
        assert "Encrypt=Yes" in conn_str

    def test_build_connection_string_custom(self) -> None:
        from sqlforensic.connectors.sqlserver import SQLServerConnector

        custom = "Server=myhost;Database=MyDB;Trusted_Connection=True;"
        config = ConnectionConfig(provider="sqlserver", connection_string=custom)
        connector = SQLServerConnector(config)
        assert connector._build_connection_string() == custom


class TestPostgreSQLConnector:
    def test_connection_error_wraps_exception(self) -> None:
        from sqlforensic.connectors.postgresql import PostgreSQLConnector

        config = ConnectionConfig(
            provider="postgresql",
            server="nonexistent",
            database="TestDB",
            username="postgres",
            password="wrong",
            port=5432,
        )
        connector = PostgreSQLConnector(config)

        mock_pg = MagicMock()
        mock_pg.connect.side_effect = Exception("Connection refused")
        mock_pg.Error = Exception
        mock_pg.extras = MagicMock()
        with patch.dict("sys.modules", {"psycopg2": mock_pg, "psycopg2.extras": mock_pg.extras}):
            with pytest.raises(ConnectionError, match="Failed to connect"):
                connector.connect()

    def test_execute_query_without_connection_raises(self) -> None:
        from sqlforensic.connectors.postgresql import PostgreSQLConnector

        config = ConnectionConfig(provider="postgresql", database="DB", port=5432)
        connector = PostgreSQLConnector(config)
        with pytest.raises(ConnectionError, match="Not connected"):
            connector.execute_query("SELECT 1")
