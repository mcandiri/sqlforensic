"""CLI entry point for SQLForensic using Click."""

from __future__ import annotations

import logging
import sys
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from sqlforensic import AnalysisReport, DatabaseForensic, __version__
from sqlforensic.config import ConnectionConfig
from sqlforensic.utils.formatting import (
    format_row_count,
    health_bar,
    severity_color,
)

console = Console()


def _build_config(ctx: click.Context) -> ConnectionConfig:
    """Build ConnectionConfig from Click context parameters."""
    params = ctx.ensure_object(dict)
    provider = params.get("provider", "sqlserver")
    return ConnectionConfig(
        provider=provider,
        server=params.get("server", "localhost"),
        database=params.get("database", ""),
        username=params.get("user", ""),
        password=params.get("password", ""),
        port=params.get("port") or (1433 if provider == "sqlserver" else 5432),
        connection_string=params.get("connection_string", ""),
        trusted_connection=params.get("trusted_connection", False),
        ssl=params.get("ssl", False),
    )


def _build_forensic(ctx: click.Context) -> DatabaseForensic:
    """Build DatabaseForensic instance from Click context."""
    config = _build_config(ctx)
    errors = config.validate()
    if errors:
        for err in errors:
            console.print(f"[red]Error:[/red] {err}")
        sys.exit(1)

    return DatabaseForensic(
        provider=config.provider,
        server=config.server,
        database=config.database,
        username=config.username,
        password=config.password,
        port=config.port,
        connection_string=config.connection_string,
        trusted_connection=config.trusted_connection,
        ssl=config.ssl,
    )


# Common connection options
def connection_options(func: Any) -> Any:
    """Decorator that adds common connection options to a command."""
    func = click.option(
        "--provider",
        "-p",
        default="sqlserver",
        type=click.Choice(["sqlserver", "postgresql"]),
        help="Database provider",
    )(func)
    func = click.option("--server", "-s", default="localhost", help="Server hostname")(func)
    func = click.option("--database", "-d", required=False, help="Database name")(func)
    func = click.option("--user", "-u", default="", help="Username")(func)
    func = click.option("--password", "-P", default="", hide_input=False, help="Password")(func)
    func = click.option("--port", type=int, default=None, help="Port number")(func)
    func = click.option("--connection-string", "-c", default="", help="Full connection string")(
        func
    )
    func = click.option(
        "--trusted-connection", is_flag=True, help="Use Windows trusted connection"
    )(func)
    func = click.option("--ssl", is_flag=True, help="Enable SSL/TLS")(func)
    func = click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")(func)
    return func


@click.group()
@click.version_option(version=__version__, prog_name="sqlforensic")
def main() -> None:
    """SQLForensic — Database forensics and analysis toolkit.

    Reverse-engineer undocumented databases in minutes. Analyzes schema,
    discovers hidden relationships, detects dead code, finds missing
    indexes, and generates comprehensive documentation.
    """


@main.command()
@connection_options
@click.option("--output", "-o", default=None, help="Output file path")
@click.option(
    "--format",
    "-f",
    "fmt",
    default="console",
    type=click.Choice(["console", "html", "markdown", "json"]),
    help="Output format",
)
@click.pass_context
def scan(ctx: click.Context, **kwargs: Any) -> None:
    """Run a full database scan and analysis."""
    ctx.ensure_object(dict).update(kwargs)
    _configure_logging(kwargs.get("verbose", False))

    forensic = _build_forensic(ctx)
    output_path = kwargs.get("output")
    fmt = kwargs.get("fmt", "console")

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Analyzing database...", total=None)
        report = forensic.analyze()
        progress.update(task, description="Analysis complete!")

    if fmt == "console" or not output_path:
        _print_full_report(report)

    if output_path:
        if fmt == "html":
            from sqlforensic.reporters.html_reporter import HTMLReporter

            HTMLReporter(report).export(output_path)
        elif fmt == "markdown":
            from sqlforensic.reporters.markdown_reporter import MarkdownReporter

            MarkdownReporter(report).export(output_path)
        elif fmt == "json":
            from sqlforensic.reporters.json_reporter import JSONReporter

            JSONReporter(report).export(output_path)

        console.print(f"\n[green]Report saved to:[/green] {output_path}")


@main.command()
@connection_options
@click.pass_context
def schema(ctx: click.Context, **kwargs: Any) -> None:
    """Analyze database schema (tables, columns, types, constraints)."""
    ctx.ensure_object(dict).update(kwargs)
    _configure_logging(kwargs.get("verbose", False))
    forensic = _build_forensic(ctx)

    with Progress(
        SpinnerColumn(), TextColumn("[bold blue]{task.description}"), console=console
    ) as progress:
        progress.add_task("Analyzing schema...", total=None)
        result = forensic.analyze_schema()

    _print_schema_overview(result)


@main.command()
@connection_options
@click.pass_context
def relationships(ctx: click.Context, **kwargs: Any) -> None:
    """Discover FK and implicit relationships between tables."""
    ctx.ensure_object(dict).update(kwargs)
    _configure_logging(kwargs.get("verbose", False))
    forensic = _build_forensic(ctx)

    with Progress(
        SpinnerColumn(), TextColumn("[bold blue]{task.description}"), console=console
    ) as progress:
        progress.add_task("Discovering relationships...", total=None)
        result = forensic.analyze_relationships()

    _print_relationships(result)


@main.command()
@connection_options
@click.pass_context
def procedures(ctx: click.Context, **kwargs: Any) -> None:
    """Analyze stored procedures (complexity, dependencies, anti-patterns)."""
    ctx.ensure_object(dict).update(kwargs)
    _configure_logging(kwargs.get("verbose", False))
    forensic = _build_forensic(ctx)

    with Progress(
        SpinnerColumn(), TextColumn("[bold blue]{task.description}"), console=console
    ) as progress:
        progress.add_task("Analyzing stored procedures...", total=None)
        report = forensic.analyze()

    _print_sp_analysis(report.sp_analysis)


@main.command()
@connection_options
@click.pass_context
def indexes(ctx: click.Context, **kwargs: Any) -> None:
    """Analyze indexes (missing, unused, duplicates, recommendations)."""
    ctx.ensure_object(dict).update(kwargs)
    _configure_logging(kwargs.get("verbose", False))
    forensic = _build_forensic(ctx)

    with Progress(
        SpinnerColumn(), TextColumn("[bold blue]{task.description}"), console=console
    ) as progress:
        progress.add_task("Analyzing indexes...", total=None)
        result = forensic.analyze_indexes()

    _print_index_analysis(result)


@main.command()
@connection_options
@click.pass_context
def deadcode(ctx: click.Context, **kwargs: Any) -> None:
    """Detect unused tables, stored procedures, and orphan columns."""
    ctx.ensure_object(dict).update(kwargs)
    _configure_logging(kwargs.get("verbose", False))
    forensic = _build_forensic(ctx)

    with Progress(
        SpinnerColumn(), TextColumn("[bold blue]{task.description}"), console=console
    ) as progress:
        progress.add_task("Detecting dead code...", total=None)
        result = forensic.detect_dead_code()

    _print_dead_code(result)


@main.command()
@connection_options
@click.option("--output", "-o", default="dependency_graph.html", help="Output HTML file")
@click.pass_context
def graph(ctx: click.Context, **kwargs: Any) -> None:
    """Generate an interactive dependency graph (HTML)."""
    ctx.ensure_object(dict).update(kwargs)
    _configure_logging(kwargs.get("verbose", False))
    forensic = _build_forensic(ctx)
    output_path = kwargs.get("output", "dependency_graph.html")

    with Progress(
        SpinnerColumn(), TextColumn("[bold blue]{task.description}"), console=console
    ) as progress:
        progress.add_task("Building dependency graph...", total=None)
        forensic.export_dependency_graph(output_path)

    console.print(f"\n[green]Dependency graph saved to:[/green] {output_path}")


@main.command()
@connection_options
@click.option("--table", "-t", required=True, help="Table name to analyze")
@click.pass_context
def impact(ctx: click.Context, **kwargs: Any) -> None:
    """Analyze the impact of modifying a specific table."""
    ctx.ensure_object(dict).update(kwargs)
    _configure_logging(kwargs.get("verbose", False))
    forensic = _build_forensic(ctx)
    table_name = kwargs["table"]

    with Progress(
        SpinnerColumn(), TextColumn("[bold blue]{task.description}"), console=console
    ) as progress:
        progress.add_task(f"Analyzing impact on {table_name}...", total=None)
        result = forensic.impact_analysis(table_name)

    console.print(
        Panel(
            f"[bold]Impact Analysis: {result.table_name}[/bold]\n"
            f"Risk Level: [{severity_color(result.risk_level)}]{result.risk_level}[/]\n"
            f"Total affected objects: {result.total_affected}",
            title="Impact Analysis",
        )
    )

    if result.affected_sps:
        table = Table(title="Affected Stored Procedures")
        table.add_column("SP Name")
        table.add_column("Risk")
        for sp in result.affected_sps:
            table.add_row(sp["name"], sp.get("risk_level", ""))
        console.print(table)

    if result.affected_views:
        console.print(f"\n[bold]Affected Views:[/bold] {', '.join(result.affected_views)}")

    if result.affected_tables:
        console.print(f"[bold]Affected Tables:[/bold] {', '.join(result.affected_tables)}")


@main.command()
@connection_options
@click.pass_context
def health(ctx: click.Context, **kwargs: Any) -> None:
    """Calculate database health score."""
    ctx.ensure_object(dict).update(kwargs)
    _configure_logging(kwargs.get("verbose", False))
    forensic = _build_forensic(ctx)

    with Progress(
        SpinnerColumn(), TextColumn("[bold blue]{task.description}"), console=console
    ) as progress:
        progress.add_task("Calculating health score...", total=None)
        report = forensic.analyze()

    _print_health_score(report)


# ── Output Printers ──────────────────────────────────────────────────


def _print_full_report(report: AnalysisReport) -> None:
    """Print the full analysis report to console."""
    from datetime import datetime

    header = (
        f"[bold white]SQLForensic Report[/bold white]\n"
        f"Database: {report.database}\n"
        f"Provider: {report.provider}\n"
        f"Scanned: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    console.print(Panel(header, style="bold blue", expand=True))

    # Health score
    _print_health_score(report)

    # Schema overview
    _print_schema_table(report)

    # Issues
    if report.issues:
        _print_issues(report.issues)

    # Dependency hotspots
    deps = report.dependencies
    if isinstance(deps, dict) and deps.get("hotspots"):
        _print_hotspots(deps["hotspots"])


def _print_health_score(report: AnalysisReport) -> None:
    """Print health score panel."""
    bar = health_bar(report.health_score)
    console.print(
        Panel(
            f"[bold]DATABASE HEALTH SCORE: {report.health_score}/100[/bold]\n{bar}",
            style="bold green" if report.health_score >= 60 else "bold yellow",
        )
    )


def _print_schema_table(report: AnalysisReport) -> None:
    """Print schema overview table."""
    table = Table(title="Schema Overview")
    table.add_column("Metric", style="bold")
    table.add_column("Count", justify="right")

    overview = report.schema_overview
    table.add_row("Tables", str(overview.get("tables", len(report.tables))))
    table.add_row("Views", str(overview.get("views", len(report.views))))
    table.add_row(
        "Stored Procedures", str(overview.get("stored_procedures", len(report.stored_procedures)))
    )
    table.add_row("Functions", str(overview.get("functions", len(report.functions))))
    table.add_row("Indexes", str(overview.get("indexes", len(report.indexes))))
    table.add_row("Foreign Keys", str(overview.get("foreign_keys", len(report.relationships))))
    table.add_row("Total Columns", str(overview.get("total_columns", 0)))
    table.add_row("Total Rows", format_row_count(overview.get("total_rows", 0)))

    console.print(table)


def _print_issues(issues: list[dict[str, Any]]) -> None:
    """Print issues table."""
    table = Table(title="Issues Found")
    table.add_column("Issue")
    table.add_column("Severity")
    table.add_column("Count", justify="right")

    for issue in issues:
        severity = issue.get("severity", "INFO")
        table.add_row(
            issue["description"],
            f"[{severity_color(severity)}]{severity}[/]",
            str(issue.get("count", 0)),
        )

    console.print(table)


def _print_hotspots(hotspots: list[dict[str, Any]]) -> None:
    """Print dependency hotspots table."""
    table = Table(title="Top Dependency Hotspots")
    table.add_column("Table")
    table.add_column("Dependent SPs", justify="right")
    table.add_column("Risk Level")

    for hs in hotspots[:10]:
        risk = hs.get("risk_level", "LOW")
        table.add_row(
            hs["table"],
            str(hs["dependent_sp_count"]),
            f"[{severity_color(risk)}]{risk}[/]",
        )

    console.print(table)


def _print_schema_overview(result: dict[str, Any]) -> None:
    """Print schema analysis results."""
    overview = result.get("overview", {})
    table = Table(title="Schema Overview")
    table.add_column("Metric", style="bold")
    table.add_column("Count", justify="right")

    for key, value in overview.items():
        label = key.replace("_", " ").title()
        table.add_row(label, format_row_count(value) if isinstance(value, int) else str(value))

    console.print(table)

    # Show tables
    tables = result.get("tables", [])
    if tables:
        t = Table(title=f"Tables ({len(tables)})")
        t.add_column("Schema")
        t.add_column("Table")
        t.add_column("Columns", justify="right")
        t.add_column("Rows", justify="right")
        t.add_column("PK")

        for tbl in tables[:50]:
            t.add_row(
                tbl.get("TABLE_SCHEMA", ""),
                tbl.get("TABLE_NAME", ""),
                str(tbl.get("column_count", 0)),
                format_row_count(tbl.get("row_count", 0)),
                "[green]Yes[/]" if tbl.get("has_primary_key") else "[red]No[/]",
            )

        console.print(t)


def _print_relationships(result: dict[str, Any]) -> None:
    """Print relationship analysis results."""
    explicit = result.get("explicit", [])
    implicit = result.get("implicit", [])

    if explicit:
        table = Table(title=f"Foreign Key Relationships ({len(explicit)})")
        table.add_column("Parent Table")
        table.add_column("Column")
        table.add_column("Referenced Table")
        table.add_column("Referenced Column")

        for rel in explicit:
            table.add_row(
                rel.get("parent_table", ""),
                rel.get("parent_column", ""),
                rel.get("referenced_table", ""),
                rel.get("referenced_column", ""),
            )

        console.print(table)

    if implicit:
        table = Table(title=f"Implicit Relationships ({len(implicit)})")
        table.add_column("Parent Table")
        table.add_column("Column")
        table.add_column("Referenced Table")
        table.add_column("Confidence")
        table.add_column("Source")

        for rel in implicit:
            conf = rel.get("confidence", 0)
            table.add_row(
                rel.get("parent_table", ""),
                rel.get("parent_column", ""),
                rel.get("referenced_table", ""),
                f"{conf}%",
                rel.get("source", ""),
            )

        console.print(table)


def _print_sp_analysis(sp_analysis: list[dict[str, Any]]) -> None:
    """Print stored procedure analysis."""
    table = Table(title="Stored Procedure Analysis")
    table.add_column("Name")
    table.add_column("Lines", justify="right")
    table.add_column("Joins", justify="right")
    table.add_column("Tables", justify="right")
    table.add_column("Complexity")
    table.add_column("Score", justify="right")

    for sp in sp_analysis[:30]:
        cat = sp.get("complexity_category", "Simple")
        color = "red" if cat == "Complex" else ("yellow" if cat == "Medium" else "green")
        table.add_row(
            sp.get("name", ""),
            str(sp.get("line_count", 0)),
            str(sp.get("join_count", 0)),
            str(len(sp.get("referenced_tables", []))),
            f"[{color}]{cat}[/]",
            str(sp.get("complexity_score", 0)),
        )

    console.print(table)


def _print_index_analysis(result: dict[str, Any]) -> None:
    """Print index analysis results."""
    missing = result.get("missing", [])
    unused = result.get("unused", [])
    duplicates = result.get("duplicates", [])

    if missing:
        table = Table(title=f"Missing Indexes ({len(missing)})")
        table.add_column("Table")
        table.add_column("Columns")
        table.add_column("Impact", justify="right")

        for idx in missing[:20]:
            table.add_row(
                idx.get("table_name", ""),
                idx.get("equality_columns", ""),
                f"{idx.get('improvement_measure', 0):.0f}",
            )
        console.print(table)

    if unused:
        table = Table(title=f"Unused Indexes ({len(unused)})")
        table.add_column("Table")
        table.add_column("Index Name")
        table.add_column("Writes", justify="right")

        for idx in unused[:20]:
            table.add_row(
                idx.get("table_name", ""),
                idx.get("index_name", ""),
                str(idx.get("user_updates", 0)),
            )
        console.print(table)

    if duplicates:
        table = Table(title=f"Duplicate Indexes ({len(duplicates)})")
        table.add_column("Table")
        table.add_column("Index")
        table.add_column("Duplicate Of")

        for idx in duplicates:
            table.add_row(
                idx.get("table_name", ""),
                idx.get("index_name", ""),
                idx.get("duplicate_of", ""),
            )
        console.print(table)


def _print_dead_code(result: dict[str, Any]) -> None:
    """Print dead code analysis results."""
    dead_tables = result.get("dead_tables", [])
    dead_procs = result.get("dead_procedures", [])
    orphans = result.get("orphan_columns", [])
    empty = result.get("empty_tables", [])

    if dead_tables:
        table = Table(title=f"Unreferenced Tables ({len(dead_tables)})")
        table.add_column("Schema")
        table.add_column("Table")
        table.add_column("Rows", justify="right")

        for t in dead_tables:
            table.add_row(
                t.get("TABLE_SCHEMA", ""),
                t.get("TABLE_NAME", ""),
                format_row_count(t.get("row_count", 0)),
            )
        console.print(table)

    if dead_procs:
        table = Table(title=f"Unused Stored Procedures ({len(dead_procs)})")
        table.add_column("Schema")
        table.add_column("Procedure Name")

        for sp in dead_procs:
            table.add_row(sp.get("ROUTINE_SCHEMA", ""), sp.get("ROUTINE_NAME", ""))
        console.print(table)

    if orphans:
        console.print(
            f"\n[bold]Orphan Columns:[/bold] "
            f"{len(orphans)} columns not referenced in any SP or view"
        )

    if empty:
        table = Table(title=f"Empty Tables ({len(empty)})")
        table.add_column("Schema")
        table.add_column("Table")

        for t in empty:
            table.add_row(t.get("TABLE_SCHEMA", ""), t.get("TABLE_NAME", ""))
        console.print(table)


def _configure_logging(verbose: bool) -> None:
    """Configure logging level."""
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


if __name__ == "__main__":
    main()
