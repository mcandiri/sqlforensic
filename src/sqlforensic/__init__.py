"""SQLForensic — Database forensics and analysis toolkit.

Reverse-engineer undocumented databases in minutes. Connects to SQL Server
and PostgreSQL, analyzes schema, discovers hidden relationships, detects
dead code, finds missing indexes, and generates comprehensive documentation.
"""

from __future__ import annotations

__version__ = "1.0.0"

import logging
from dataclasses import dataclass, field
from typing import Any

from sqlforensic.config import AnalysisConfig, ConnectionConfig
from sqlforensic.connectors.base import BaseConnector
from sqlforensic.connectors.postgresql import PostgreSQLConnector
from sqlforensic.connectors.sqlserver import SQLServerConnector

logger = logging.getLogger(__name__)


@dataclass
class AnalysisReport:
    """Complete analysis report with all results."""

    database: str = ""
    provider: str = ""
    health_score: int = 0
    tables: list[dict[str, Any]] = field(default_factory=list)
    views: list[dict[str, Any]] = field(default_factory=list)
    stored_procedures: list[dict[str, Any]] = field(default_factory=list)
    functions: list[dict[str, Any]] = field(default_factory=list)
    relationships: list[dict[str, Any]] = field(default_factory=list)
    implicit_relationships: list[dict[str, Any]] = field(default_factory=list)
    indexes: list[dict[str, Any]] = field(default_factory=list)
    missing_indexes: list[dict[str, Any]] = field(default_factory=list)
    unused_indexes: list[dict[str, Any]] = field(default_factory=list)
    duplicate_indexes: list[dict[str, Any]] = field(default_factory=list)
    dead_procedures: list[dict[str, Any]] = field(default_factory=list)
    dead_tables: list[dict[str, Any]] = field(default_factory=list)
    orphan_columns: list[dict[str, Any]] = field(default_factory=list)
    empty_tables: list[dict[str, Any]] = field(default_factory=list)
    dependencies: dict[str, Any] = field(default_factory=dict)
    circular_dependencies: list[list[str]] = field(default_factory=list)
    issues: list[dict[str, Any]] = field(default_factory=list)
    sp_analysis: list[dict[str, Any]] = field(default_factory=list)
    size_info: list[dict[str, Any]] = field(default_factory=list)
    security_issues: list[dict[str, Any]] = field(default_factory=list)
    risk_scores: dict[str, Any] = field(default_factory=dict)
    schema_overview: dict[str, int] = field(default_factory=dict)


@dataclass
class ImpactResult:
    """Result of an impact analysis on a specific table."""

    table_name: str = ""
    affected_sps: list[dict[str, Any]] = field(default_factory=list)
    affected_views: list[str] = field(default_factory=list)
    affected_tables: list[str] = field(default_factory=list)
    risk_level: str = "LOW"
    total_affected: int = 0


class DatabaseForensic:
    """Main entry point for SQLForensic library API.

    Connects to a database and provides methods to analyze schema,
    relationships, stored procedures, indexes, and more.

    Example:
        >>> forensic = DatabaseForensic(
        ...     provider="sqlserver",
        ...     server="localhost",
        ...     database="MyDB",
        ...     username="sa",
        ...     password="secret"
        ... )
        >>> report = forensic.analyze()
        >>> print(f"Health Score: {report.health_score}/100")
    """

    def __init__(
        self,
        provider: str = "sqlserver",
        server: str = "localhost",
        database: str = "",
        username: str = "",
        password: str = "",
        port: int | None = None,
        connection_string: str = "",
        trusted_connection: bool = False,
        ssl: bool = False,
    ) -> None:
        self.connection_config = ConnectionConfig(
            provider=provider,
            server=server,
            database=database,
            username=username,
            password=password,
            port=port or (1433 if provider == "sqlserver" else 5432),
            connection_string=connection_string,
            trusted_connection=trusted_connection,
            ssl=ssl,
        )
        self.analysis_config = AnalysisConfig()
        self._connector: BaseConnector | None = None

    def _get_connector(self) -> BaseConnector:
        """Get or create the database connector."""
        if self._connector is None:
            if self.connection_config.provider == "sqlserver":
                self._connector = SQLServerConnector(self.connection_config)
            elif self.connection_config.provider == "postgresql":
                self._connector = PostgreSQLConnector(self.connection_config)
            else:
                raise ValueError(f"Unsupported provider: {self.connection_config.provider}")
        return self._connector

    def analyze(self) -> AnalysisReport:
        """Run full database analysis and return comprehensive report.

        Raises:
            ConnectionError: If the database connection fails.
            RuntimeError: If a critical analyzer fails.
        """
        from sqlforensic.analyzers.dead_code_analyzer import DeadCodeAnalyzer
        from sqlforensic.analyzers.dependency_analyzer import DependencyAnalyzer
        from sqlforensic.analyzers.index_analyzer import IndexAnalyzer
        from sqlforensic.analyzers.relationship_analyzer import RelationshipAnalyzer
        from sqlforensic.analyzers.schema_analyzer import SchemaAnalyzer
        from sqlforensic.analyzers.security_analyzer import SecurityAnalyzer
        from sqlforensic.analyzers.size_analyzer import SizeAnalyzer
        from sqlforensic.analyzers.sp_analyzer import SPAnalyzer
        from sqlforensic.scoring.health_score import HealthScoreCalculator
        from sqlforensic.scoring.risk_scorer import RiskScorer

        connector = self._get_connector()
        connector.connect()

        try:
            report = AnalysisReport(
                database=self.connection_config.database,
                provider=self.connection_config.provider,
            )

            # Schema analysis is critical — failure here is unrecoverable
            schema = SchemaAnalyzer(connector)
            schema_result = schema.analyze()
            report.tables = schema_result.get("tables", [])
            report.views = schema_result.get("views", [])
            report.stored_procedures = schema_result.get("stored_procedures", [])
            report.functions = schema_result.get("functions", [])
            report.indexes = schema_result.get("indexes", [])
            report.schema_overview = schema_result.get("overview", {})

            rel = RelationshipAnalyzer(connector, report.tables, report.stored_procedures)
            rel_result = rel.analyze()
            report.relationships = rel_result.get("explicit", [])
            report.implicit_relationships = rel_result.get("implicit", [])

            sp = SPAnalyzer(connector, report.stored_procedures)
            report.sp_analysis = sp.analyze()

            idx = IndexAnalyzer(connector)
            idx_result = idx.analyze()
            report.missing_indexes = idx_result.get("missing", [])
            report.unused_indexes = idx_result.get("unused", [])
            report.duplicate_indexes = idx_result.get("duplicates", [])

            dead = DeadCodeAnalyzer(
                report.tables, report.stored_procedures, report.relationships, report.views
            )
            dead_result = dead.analyze()
            report.dead_procedures = dead_result.get("dead_procedures", [])
            report.dead_tables = dead_result.get("dead_tables", [])
            report.orphan_columns = dead_result.get("orphan_columns", [])
            report.empty_tables = dead_result.get("empty_tables", [])

            dep = DependencyAnalyzer(
                report.tables, report.stored_procedures, report.relationships, report.views
            )
            dep_result = dep.analyze()
            report.dependencies = dep_result.get("graph", {})
            report.circular_dependencies = dep_result.get("circular", [])

            # Non-critical analyzers: log errors but continue
            try:
                size = SizeAnalyzer(connector)
                report.size_info = size.analyze()
            except Exception:
                logger.warning("Size analysis failed, skipping", exc_info=True)

            try:
                sec = SecurityAnalyzer(connector)
                report.security_issues = sec.analyze()
            except Exception:
                logger.warning("Security analysis failed, skipping", exc_info=True)

            scorer = HealthScoreCalculator(report)
            report.health_score = scorer.calculate()
            report.issues = scorer.get_issues()

            risk = RiskScorer(report)
            report.risk_scores = risk.calculate()

            return report
        finally:
            connector.disconnect()

    def analyze_schema(self) -> dict[str, Any]:
        """Run schema analysis only."""
        from sqlforensic.analyzers.schema_analyzer import SchemaAnalyzer

        connector = self._get_connector()
        connector.connect()
        try:
            return SchemaAnalyzer(connector).analyze()
        finally:
            connector.disconnect()

    def analyze_relationships(self) -> dict[str, Any]:
        """Run relationship discovery."""
        from sqlforensic.analyzers.relationship_analyzer import RelationshipAnalyzer
        from sqlforensic.analyzers.schema_analyzer import SchemaAnalyzer

        connector = self._get_connector()
        connector.connect()
        try:
            schema = SchemaAnalyzer(connector).analyze()
            return RelationshipAnalyzer(
                connector, schema["tables"], schema["stored_procedures"]
            ).analyze()
        finally:
            connector.disconnect()

    def detect_dead_code(self) -> dict[str, Any]:
        """Run dead code detection."""
        from sqlforensic.analyzers.dead_code_analyzer import DeadCodeAnalyzer
        from sqlforensic.analyzers.relationship_analyzer import RelationshipAnalyzer
        from sqlforensic.analyzers.schema_analyzer import SchemaAnalyzer

        connector = self._get_connector()
        connector.connect()
        try:
            schema = SchemaAnalyzer(connector).analyze()
            rel = RelationshipAnalyzer(
                connector, schema["tables"], schema["stored_procedures"]
            ).analyze()
            return DeadCodeAnalyzer(
                schema["tables"], schema["stored_procedures"], rel["explicit"], schema["views"]
            ).analyze()
        finally:
            connector.disconnect()

    def analyze_dependencies(self) -> dict[str, Any]:
        """Run dependency analysis."""
        from sqlforensic.analyzers.dependency_analyzer import DependencyAnalyzer
        from sqlforensic.analyzers.relationship_analyzer import RelationshipAnalyzer
        from sqlforensic.analyzers.schema_analyzer import SchemaAnalyzer

        connector = self._get_connector()
        connector.connect()
        try:
            schema = SchemaAnalyzer(connector).analyze()
            rel = RelationshipAnalyzer(
                connector, schema["tables"], schema["stored_procedures"]
            ).analyze()
            return DependencyAnalyzer(
                schema["tables"], schema["stored_procedures"], rel["explicit"], schema["views"]
            ).analyze()
        finally:
            connector.disconnect()

    def analyze_indexes(self) -> dict[str, Any]:
        """Run index analysis."""
        from sqlforensic.analyzers.index_analyzer import IndexAnalyzer

        connector = self._get_connector()
        connector.connect()
        try:
            return IndexAnalyzer(connector).analyze()
        finally:
            connector.disconnect()

    def impact_analysis(self, table_name: str) -> ImpactResult:
        """Analyze the impact of modifying a specific table."""
        from sqlforensic.analyzers.dependency_analyzer import DependencyAnalyzer
        from sqlforensic.analyzers.relationship_analyzer import RelationshipAnalyzer
        from sqlforensic.analyzers.schema_analyzer import SchemaAnalyzer

        connector = self._get_connector()
        connector.connect()
        try:
            schema = SchemaAnalyzer(connector).analyze()
            rel = RelationshipAnalyzer(
                connector, schema["tables"], schema["stored_procedures"]
            ).analyze()
            dep = DependencyAnalyzer(
                schema["tables"], schema["stored_procedures"], rel["explicit"], schema["views"]
            )
            dep_result = dep.analyze()
            return dep.get_impact(table_name, dep_result)
        finally:
            connector.disconnect()

    def export_html(self, output_path: str) -> None:
        """Run full analysis and export as HTML report."""
        from sqlforensic.reporters.html_reporter import HTMLReporter

        report = self.analyze()
        HTMLReporter(report).export(output_path)

    def export_markdown(self, output_path: str) -> None:
        """Run full analysis and export as Markdown."""
        from sqlforensic.reporters.markdown_reporter import MarkdownReporter

        report = self.analyze()
        MarkdownReporter(report).export(output_path)

    def export_json(self, output_path: str) -> None:
        """Run full analysis and export as JSON."""
        from sqlforensic.reporters.json_reporter import JSONReporter

        report = self.analyze()
        JSONReporter(report).export(output_path)

    def export_dependency_graph(self, output_path: str) -> None:
        """Run full analysis and export interactive dependency graph."""
        from sqlforensic.reporters.html_reporter import HTMLReporter

        report = self.analyze()
        HTMLReporter(report).export_graph(output_path)


__all__ = [
    "DatabaseForensic",
    "AnalysisReport",
    "ImpactResult",
    "ConnectionConfig",
    "AnalysisConfig",
    "__version__",
]
