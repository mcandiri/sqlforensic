"""HTML report exporter with interactive dashboard and D3.js dependency graph."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import TYPE_CHECKING

from jinja2 import Environment, FileSystemLoader, select_autoescape

from sqlforensic.utils.formatting import format_row_count, format_size

if TYPE_CHECKING:
    from sqlforensic import AnalysisReport

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")


class HTMLReporter:
    """Export analysis results as a self-contained interactive HTML report.

    The report is a single HTML file with inline CSS and JS (except D3.js from CDN).
    It includes a dashboard, schema browser, dependency graph, issues table,
    SP analysis, and index recommendations.
    """

    def __init__(self, report: AnalysisReport) -> None:
        self.report = report
        self.env = Environment(
            loader=FileSystemLoader(TEMPLATE_DIR),
            autoescape=select_autoescape(["html"]),
        )
        self.env.filters["row_count"] = format_row_count
        self.env.filters["file_size"] = format_size

    def export(self, output_path: str) -> None:
        """Export full HTML report.

        Args:
            output_path: Path to write the HTML file.
        """
        template = self.env.get_template("report.html")
        html = template.render(
            report=self.report,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            graph_data=self._build_graph_json(),
            css=self._load_asset("assets/style.css"),
            graph_js=self._load_asset("assets/graph.js"),
        )

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

    def export_graph(self, output_path: str) -> None:
        """Export only the interactive dependency graph.

        Args:
            output_path: Path to write the HTML file.
        """
        template = self.env.get_template("dependency_graph.html")
        html = template.render(
            report=self.report,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            graph_data=self._build_graph_json(),
            css=self._load_asset("assets/style.css"),
            graph_js=self._load_asset("assets/graph.js"),
        )

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

    def _build_graph_json(self) -> str:
        """Build JSON data for the D3.js dependency graph."""
        deps = self.report.dependencies
        if not isinstance(deps, dict):
            return json.dumps({"nodes": [], "links": []})

        nodes_raw = deps.get("nodes", [])
        edges_raw = deps.get("edges", [])

        # Build node set
        node_ids = {n["id"] for n in nodes_raw}
        nodes = []
        for n in nodes_raw:
            criticality = n.get("in_degree", 0) + n.get("out_degree", 0)
            nodes.append(
                {
                    "id": n["id"],
                    "type": n.get("type", "unknown"),
                    "criticality": criticality,
                }
            )

        # Build link set (only include links where both nodes exist)
        links = []
        for e in edges_raw:
            if e["source"] in node_ids and e["target"] in node_ids:
                links.append(
                    {
                        "source": e["source"],
                        "target": e["target"],
                        "type": e.get("type", ""),
                    }
                )

        return json.dumps({"nodes": nodes, "links": links}, default=str)

    def _load_asset(self, relative_path: str) -> str:
        """Load an asset file from the templates directory."""
        path = os.path.join(TEMPLATE_DIR, relative_path)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return f.read()
        return ""
