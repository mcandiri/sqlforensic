"""Console reporter for schema diff results — Rich terminal output.

Renders a DiffResult as colorful, formatted terminal output with
summary tables, risk assessments, and migration recommendations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from sqlforensic.utils.formatting import severity_color

if TYPE_CHECKING:
    from sqlforensic.diff.diff_result import DiffResult


_RISK_COLORS: dict[str, str] = {
    "CRITICAL": "bold red",
    "HIGH": "red",
    "MEDIUM": "yellow",
    "LOW": "cyan",
    "NONE": "dim",
}


class DiffConsoleReporter:
    """Render schema diff results to the terminal using Rich.

    Produces colorful, formatted terminal output including a summary
    dashboard, risk assessment table, and migration recommendations.
    """

    def __init__(self, diff: DiffResult, console: Console | None = None) -> None:
        self.diff = diff
        self.console = console or Console()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def print_report(self) -> None:
        """Print the full diff report to the console."""
        self._print_header()
        self._print_summary()
        self._print_risk_assessment()
        self._print_migration_info()
        self._print_recommendations()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _risk_style(self, level: str) -> str:
        """Return the Rich style string for a risk level."""
        return _RISK_COLORS.get(level.upper(), "dim")

    def _print_header(self) -> None:
        """Print report header panel with source/target database names."""
        from datetime import datetime

        risk = self.diff.risk_level
        risk_style = self._risk_style(risk)

        self.console.print(
            Panel(
                f"[bold white]SQLForensic — Schema Diff Report[/]\n"
                f"\n"
                f"Source : [bold]{self.diff.source_database}[/]"
                f"{'  (' + self.diff.source_server + ')' if self.diff.source_server else ''}\n"
                f"Target : [bold]{self.diff.target_database}[/]"
                f"{'  (' + self.diff.target_server + ')' if self.diff.target_server else ''}\n"
                f"Provider: {self.diff.provider or 'N/A'}\n"
                f"Scanned : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"\n"
                f"Overall Risk: [{risk_style}]{risk}[/]   "
                f"Total Changes: [bold]{self.diff.total_changes}[/]",
                style="bold blue",
            )
        )

    def _print_summary(self) -> None:
        """Print summary table: Object Type | Added | Removed | Modified."""
        summary = self.diff.summary

        table = Table(title="Change Summary")
        table.add_column("Object Type", style="bold")
        table.add_column("Added", justify="right", style="green")
        table.add_column("Removed", justify="right", style="red")
        table.add_column("Modified", justify="right", style="yellow")

        has_any = False
        for category, counts in summary.items():
            added = counts.get("Added", 0)
            removed = counts.get("Removed", 0)
            modified = counts.get("Modified", 0)
            if added or removed or modified:
                has_any = True
            table.add_row(
                category,
                str(added) if added else "-",
                str(removed) if removed else "-",
                str(modified) if modified else "-",
            )

        if not has_any:
            self.console.print(Panel("[dim]No schema differences detected.[/]", style="dim"))
            return

        self.console.print(table)

    def _print_risk_assessment(self) -> None:
        """Print risk assessment table: Change | Risk | Affected Objects."""
        if not self.diff.risks:
            return

        table = Table(title="Risk Assessment")
        table.add_column("Change", style="bold", max_width=50)
        table.add_column("Risk Level", justify="center")
        table.add_column("Score", justify="right")
        table.add_column("Affected Objects", max_width=40)

        for risk in self.diff.risks:
            level = risk.risk_level
            style = self._risk_style(level)
            affected = ", ".join(risk.affected_objects[:5]) if risk.affected_objects else "-"
            if len(risk.affected_objects) > 5:
                affected += f" (+{len(risk.affected_objects) - 5} more)"

            table.add_row(
                risk.change_description,
                f"[{style}]{level}[/]",
                f"{risk.risk_score:.0f}",
                affected,
            )

        self.console.print(table)

        # Print breaking changes if any exist
        breaking = [change for risk in self.diff.risks for change in risk.breaking_changes]
        if breaking:
            self.console.print()
            self.console.print(
                Panel(
                    "[bold red]Breaking Changes Detected[/]\n\n"
                    + "\n".join(f"  [red]\u2022[/] {bc}" for bc in breaking),
                    style="red",
                )
            )

    def _print_migration_info(self) -> None:
        """Print migration script information line."""
        if not self.diff.has_changes:
            return

        # Count detailed changes for the info line
        table_adds = len(self.diff.tables.added_tables)
        table_drops = len(self.diff.tables.removed_tables)
        table_alters = len(self.diff.tables.modified_tables)
        idx_adds = len(self.diff.indexes.added_indexes)
        idx_drops = len(self.diff.indexes.removed_indexes)
        sp_changes = (
            len(self.diff.procedures.added)
            + len(self.diff.procedures.removed)
            + len(self.diff.procedures.modified)
        )
        fk_changes = len(self.diff.foreign_keys_added) + len(self.diff.foreign_keys_removed)

        parts: list[str] = []
        if table_adds:
            parts.append(f"{table_adds} CREATE TABLE")
        if table_drops:
            parts.append(f"{table_drops} DROP TABLE")
        if table_alters:
            parts.append(f"{table_alters} ALTER TABLE")
        if idx_adds:
            parts.append(f"{idx_adds} CREATE INDEX")
        if idx_drops:
            parts.append(f"{idx_drops} DROP INDEX")
        if sp_changes:
            parts.append(f"{sp_changes} procedure changes")
        if fk_changes:
            parts.append(f"{fk_changes} FK changes")

        migration_detail = ", ".join(parts) if parts else "No migration statements"

        self.console.print()
        self.console.print(
            Panel(
                f"[bold]Migration Summary[/]\n\n"
                f"  Estimated statements: {migration_detail}\n"
                f"  Total changes: [bold]{self.diff.total_changes}[/]",
                style="blue",
            )
        )

    def _print_recommendations(self) -> None:
        """Print actionable recommendations from risk assessments."""
        all_recommendations: list[str] = []
        seen: set[str] = set()
        for risk in self.diff.risks:
            for rec in risk.recommendations:
                if rec not in seen:
                    all_recommendations.append(rec)
                    seen.add(rec)

        if not all_recommendations:
            return

        self.console.print()
        lines = "\n".join(
            f"  [{severity_color('MEDIUM')}]\u2022[/] {rec}" for rec in all_recommendations
        )
        self.console.print(
            Panel(
                f"[bold]Recommendations[/]\n\n{lines}",
                style="yellow",
            )
        )
