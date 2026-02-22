"""Configuration classes for SQLForensic connections and analysis settings."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ConnectionConfig:
    """Database connection configuration.

    Attributes:
        provider: Database provider ('sqlserver' or 'postgresql').
        server: Server hostname or IP address.
        database: Database name to analyze.
        username: Login username.
        password: Login password (never logged or stored).
        port: Connection port.
        connection_string: Full connection string (overrides individual params).
        trusted_connection: Use Windows authentication (SQL Server).
        ssl: Enable SSL/TLS for the connection.
    """

    provider: str = "sqlserver"
    server: str = "localhost"
    database: str = ""
    username: str = ""
    password: str = ""
    port: int = 1433
    connection_string: str = ""
    trusted_connection: bool = False
    ssl: bool = False

    def __repr__(self) -> str:
        """Return string representation with password masked."""
        return (
            f"ConnectionConfig(provider={self.provider!r}, server={self.server!r}, "
            f"database={self.database!r}, username={self.username!r}, password='***', "
            f"port={self.port}, trusted_connection={self.trusted_connection}, ssl={self.ssl})"
        )

    def get_masked_connection_info(self) -> str:
        """Return connection info with password masked for logging."""
        if self.connection_string:
            import re

            return re.sub(
                r"(password|pwd)\s*=\s*[^;]+",
                r"\1=***",
                self.connection_string,
                flags=re.IGNORECASE,
            )
        return f"{self.provider}://{self.username}:***@{self.server}:{self.port}/{self.database}"

    def validate(self) -> list[str]:
        """Validate configuration and return list of errors."""
        errors: list[str] = []
        if self.provider not in ("sqlserver", "postgresql"):
            errors.append(f"Unsupported provider: {self.provider}")
        if not (1 <= self.port <= 65535):
            errors.append(f"Port must be between 1 and 65535, got {self.port}")
        if not self.connection_string:
            if not self.database:
                errors.append("Database name is required")
            if not self.trusted_connection and not self.username:
                errors.append("Username is required (or use trusted_connection)")
        return errors


@dataclass
class AnalysisConfig:
    """Configuration for analysis behavior.

    Attributes:
        include_schemas: Schemas to include (empty = all).
        exclude_schemas: Schemas to exclude from analysis.
        max_sp_size: Max stored procedure body size to parse (bytes).
        detect_implicit_relationships: Enable naming-convention relationship detection.
        implicit_confidence_threshold: Minimum confidence for implicit relationships (0-100).
        analyze_security: Include security analysis.
        analyze_sizes: Include size analysis.
    """

    include_schemas: list[str] = field(default_factory=list)
    exclude_schemas: list[str] = field(
        default_factory=lambda: ["sys", "INFORMATION_SCHEMA", "pg_catalog", "pg_toast"]
    )
    max_sp_size: int = 1_000_000
    detect_implicit_relationships: bool = True
    implicit_confidence_threshold: int = 50
    analyze_security: bool = True
    analyze_sizes: bool = True
