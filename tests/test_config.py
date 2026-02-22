"""Tests for ConnectionConfig and AnalysisConfig."""

from __future__ import annotations

from sqlforensic.config import AnalysisConfig, ConnectionConfig


class TestConnectionConfig:
    """Tests for ConnectionConfig validation and security."""

    def test_valid_config_returns_no_errors(self) -> None:
        config = ConnectionConfig(
            provider="sqlserver",
            server="localhost",
            database="TestDB",
            username="sa",
            password="pw",
            port=1433,
        )
        assert config.validate() == []

    def test_missing_database_returns_error(self) -> None:
        config = ConnectionConfig(provider="sqlserver", username="sa")
        errors = config.validate()
        assert any("Database" in e for e in errors)

    def test_missing_username_returns_error(self) -> None:
        config = ConnectionConfig(provider="sqlserver", database="TestDB")
        errors = config.validate()
        assert any("Username" in e or "username" in e for e in errors)

    def test_trusted_connection_skips_username_check(self) -> None:
        config = ConnectionConfig(
            provider="sqlserver",
            database="TestDB",
            trusted_connection=True,
        )
        errors = config.validate()
        assert not any("username" in e.lower() for e in errors)

    def test_invalid_provider_returns_error(self) -> None:
        config = ConnectionConfig(provider="mysql", database="TestDB", username="u")
        errors = config.validate()
        assert any("provider" in e.lower() or "mysql" in e for e in errors)

    def test_invalid_port_zero(self) -> None:
        config = ConnectionConfig(
            provider="sqlserver",
            database="DB",
            username="u",
            port=0,
        )
        errors = config.validate()
        assert any("port" in e.lower() or "Port" in e for e in errors)

    def test_invalid_port_too_high(self) -> None:
        config = ConnectionConfig(
            provider="sqlserver",
            database="DB",
            username="u",
            port=70000,
        )
        errors = config.validate()
        assert any("port" in e.lower() or "Port" in e for e in errors)

    def test_connection_string_skips_db_and_user_check(self) -> None:
        config = ConnectionConfig(
            provider="sqlserver",
            connection_string="Server=localhost;Database=X;User=sa;Password=pw",
        )
        assert config.validate() == []

    def test_repr_masks_password(self) -> None:
        config = ConnectionConfig(password="super-secret-123")
        r = repr(config)
        assert "super-secret-123" not in r
        assert "***" in r

    def test_get_masked_connection_info_masks_password(self) -> None:
        config = ConnectionConfig(
            provider="sqlserver",
            server="srv",
            database="DB",
            username="user",
            password="secret",
            port=1433,
        )
        info = config.get_masked_connection_info()
        assert "secret" not in info
        assert "***" in info

    def test_get_masked_connection_string(self) -> None:
        config = ConnectionConfig(
            connection_string="Server=srv;Password=hunter2;Database=DB",
        )
        info = config.get_masked_connection_info()
        assert "hunter2" not in info

    def test_postgresql_config_valid(self) -> None:
        config = ConnectionConfig(
            provider="postgresql",
            server="localhost",
            database="TestDB",
            username="postgres",
            port=5432,
        )
        assert config.validate() == []


class TestAnalysisConfig:
    """Tests for AnalysisConfig defaults."""

    def test_default_exclude_schemas(self) -> None:
        config = AnalysisConfig()
        assert "sys" in config.exclude_schemas
        assert "pg_catalog" in config.exclude_schemas

    def test_default_values(self) -> None:
        config = AnalysisConfig()
        assert config.detect_implicit_relationships is True
        assert config.implicit_confidence_threshold == 50
        assert config.max_sp_size == 1_000_000
