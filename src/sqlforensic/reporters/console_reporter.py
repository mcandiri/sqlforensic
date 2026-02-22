"""Console reporter — Rich terminal output.

The console output is handled directly in cli.py using Rich.
This module provides a reusable class for programmatic console output.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from sqlforensic.utils.formatting import format_row_count, health_bar, severity_color

if TYPE_CHECKING:
    from sqlforensic import AnalysisReport


class ConsoleReporter:
    """Render analysis results to the terminal using Rich.

    Produces colorful, formatted terminal output with tables,
    panels, and progress indicators.
    """

    def __init__(self, report: AnalysisReport, console: Console | None = None) -> None:
        self.report = report
        self.console = console or Console()

    def print_report(self) -> None:
        """Print the full analysis report to the console."""
        self._print_header()
        self._print_health()
        self._print_overview()
        self._print_issues()
        self._print_hotspots()

    def _print_header(self) -> None:
        """Print report header."""
        from datetime import datetime

        self.console.print(
            Panel(
                f"[bold white]SQLForensic Report[/]\n"
                f"Database: {self.report.database}\n"
                f"Provider: {self.report.provider}\n"
                f"Scanned: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                style="bold blue",
            )
        )

    def _print_health(self) -> None:
        """Print health score."""
        bar = health_bar(self.report.health_score)
        style = "bold green" if self.report.health_score >= 60 else "bold yellow"
        self.console.print(
            Panel(
                f"[bold]DATABASE HEALTH SCORE: {self.report.health_score}/100[/]\n{bar}",
                style=style,
            )
        )

    def _print_overview(self) -> None:
        """Print schema overview table."""
        table = Table(title="Schema Overview")
        table.add_column("Metric", style="bold")
        table.add_column("Count", justify="right")

        overview = self.report.schema_overview
        for key, value in overview.items():
            label = key.replace("_", " ").title()
            display = format_row_count(value) if isinstance(value, int) else str(value)
            table.add_row(label, display)

        self.console.print(table)

    def _print_issues(self) -> None:
        """Print issues table."""
        if not self.report.issues:
            return

        table = Table(title="Issues Found")
        table.add_column("Issue")
        table.add_column("Severity")
        table.add_column("Count", justify="right")

        for issue in self.report.issues:
            sev = issue.get("severity", "INFO")
            table.add_row(
                issue["description"],
                f"[{severity_color(sev)}]{sev}[/]",
                str(issue.get("count", 0)),
            )

        self.console.print(table)

    def _print_hotspots(self) -> None:
        """Print dependency hotspots."""
        deps = self.report.dependencies
        if not isinstance(deps, dict) or not deps.get("hotspots"):
            return

        table = Table(title="Top Dependency Hotspots")
        table.add_column("Table")
        table.add_column("Dependent SPs", justify="right")
        table.add_column("Risk Level")

        for hs in deps["hotspots"][:10]:
            risk = hs.get("risk_level", "LOW")
            table.add_row(
                hs["table"],
                str(hs["dependent_sp_count"]),
                f"[{severity_color(risk)}]{risk}[/]",
            )

        self.console.print(table)
