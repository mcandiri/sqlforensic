"""HTML report exporter for schema diff results.

Generates a self-contained interactive HTML report showing all schema
differences, risk assessments, and migration information.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import TYPE_CHECKING

from jinja2 import Environment, FileSystemLoader, select_autoescape

if TYPE_CHECKING:
    from sqlforensic.diff.diff_result import DiffResult

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")


class DiffHTMLReporter:
    """Export schema diff results as a self-contained interactive HTML report.

    The report is a single HTML file with all CSS and JS inline.
    It includes a summary dashboard, change list, risk assessment,
    and migration information.
    """

    def __init__(self, diff: DiffResult) -> None:
        self.diff = diff
        self.env = Environment(
            loader=FileSystemLoader(TEMPLATE_DIR),
            autoescape=select_autoescape(["html"]),
        )

    def export(self, output_path: str) -> None:
        """Export full HTML diff report.

        Args:
            output_path: Path to write the HTML file.
        """
        template = self.env.get_template("diff_report.html")
        html = template.render(
            diff=self.diff,
            summary=self.diff.summary,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
