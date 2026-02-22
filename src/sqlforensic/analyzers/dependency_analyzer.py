"""Dependency analyzer — builds dependency graph, detects cycles, calculates criticality."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

import networkx as nx

if TYPE_CHECKING:
    from sqlforensic import ImpactResult

logger = logging.getLogger(__name__)


class DependencyAnalyzer:
    """Build and analyze the full dependency graph of the database.

    Creates a directed graph where:
    - Nodes are tables, SPs, and views
    - Edges represent dependencies (FK, SP references, view references)

    Detects circular dependencies, calculates criticality scores,
    and identifies isolated clusters.
    """

    def __init__(
        self,
        tables: list[dict[str, Any]],
        stored_procedures: list[dict[str, Any]],
        foreign_keys: list[dict[str, Any]],
        views: list[dict[str, Any]],
    ) -> None:
        self.tables = tables
        self.stored_procedures = stored_procedures
        self.foreign_keys = foreign_keys
        self.views = views
        self._graph: nx.DiGraph = nx.DiGraph()

    def analyze(self) -> dict[str, Any]:
        """Build dependency graph and run analysis.

        Returns:
            Dict with 'graph', 'circular', 'criticality', and 'clusters' keys.
        """
        logger.info("Starting dependency analysis")

        self._build_graph()
        circular = self._detect_circular_dependencies()
        criticality = self._calculate_criticality()
        clusters = self._find_clusters()
        hotspots = self._find_hotspots()

        graph_data = {
            "nodes": [
                {
                    "id": node,
                    "type": self._graph.nodes[node].get("type", "unknown"),
                    "in_degree": self._graph.in_degree(node),
                    "out_degree": self._graph.out_degree(node),
                }
                for node in self._graph.nodes
            ],
            "edges": [
                {
                    "source": u,
                    "target": v,
                    "type": self._graph.edges[u, v].get("type", ""),
                }
                for u, v in self._graph.edges
            ],
        }

        logger.info(
            "Dependency analysis complete: %d nodes, %d edges, %d cycles",
            len(graph_data["nodes"]),
            len(graph_data["edges"]),
            len(circular),
        )

        return {
            "graph": graph_data,
            "circular": circular,
            "criticality": criticality,
            "clusters": clusters,
            "hotspots": hotspots,
        }

    def _build_graph(self) -> None:
        """Construct the dependency graph from all sources."""
        # Add table nodes
        for table in self.tables:
            name = table.get("TABLE_NAME", "")
            self._graph.add_node(name, type="table", schema=table.get("TABLE_SCHEMA", ""))

        # Add SP nodes and their table dependencies
        for sp in self.stored_procedures:
            sp_name = sp.get("ROUTINE_NAME", "")
            self._graph.add_node(sp_name, type="procedure", schema=sp.get("ROUTINE_SCHEMA", ""))

            body = sp.get("ROUTINE_DEFINITION") or ""
            for table in self.tables:
                table_name = table.get("TABLE_NAME", "")
                if table_name and re.search(rf"\b{re.escape(table_name)}\b", body, re.IGNORECASE):
                    self._graph.add_edge(sp_name, table_name, type="references")

        # Add view nodes and dependencies
        for view in self.views:
            view_name = view.get("TABLE_NAME", "")
            self._graph.add_node(view_name, type="view", schema=view.get("TABLE_SCHEMA", ""))

            definition = view.get("VIEW_DEFINITION") or ""
            for table in self.tables:
                table_name = table.get("TABLE_NAME", "")
                if table_name and re.search(
                    rf"\b{re.escape(table_name)}\b", definition, re.IGNORECASE
                ):
                    self._graph.add_edge(view_name, table_name, type="references")

        # Add FK edges between tables
        for fk in self.foreign_keys:
            parent = fk.get("parent_table", "")
            referenced = fk.get("referenced_table", "")
            if parent and referenced:
                self._graph.add_edge(parent, referenced, type="foreign_key")

        # Add SP-to-SP call dependencies
        sp_names = {sp.get("ROUTINE_NAME", "") for sp in self.stored_procedures}
        for sp in self.stored_procedures:
            body = sp.get("ROUTINE_DEFINITION") or ""
            sp_name = sp.get("ROUTINE_NAME", "")
            for other_name in sp_names:
                if (
                    other_name != sp_name
                    and other_name
                    and re.search(rf"\b{re.escape(other_name)}\b", body, re.IGNORECASE)
                ):
                    self._graph.add_edge(sp_name, other_name, type="calls")

    def _detect_circular_dependencies(self) -> list[list[str]]:
        """Find all circular dependency cycles in the graph."""
        try:
            cycles = list(nx.simple_cycles(self._graph))
            # Filter to only meaningful cycles (length >= 2)
            return [cycle for cycle in cycles if len(cycle) >= 2]
        except nx.NetworkXError:
            return []

    def _calculate_criticality(self) -> list[dict[str, Any]]:
        """Calculate criticality score for each node based on dependencies."""
        criticality: list[dict[str, Any]] = []

        for node in self._graph.nodes:
            in_deg = self._graph.in_degree(node)
            out_deg = self._graph.out_degree(node)

            # Nodes that many other nodes depend on are more critical
            dependents = len(list(nx.ancestors(self._graph, node)))
            total_score = in_deg * 3 + dependents * 2 + out_deg

            criticality.append(
                {
                    "name": node,
                    "type": self._graph.nodes[node].get("type", "unknown"),
                    "score": total_score,
                    "in_degree": in_deg,
                    "out_degree": out_deg,
                    "dependent_count": dependents,
                }
            )

        return sorted(criticality, key=lambda x: x["score"], reverse=True)

    def _find_clusters(self) -> list[list[str]]:
        """Find isolated clusters of objects that don't interact."""
        undirected = self._graph.to_undirected()
        components = list(nx.connected_components(undirected))
        return [sorted(list(comp)) for comp in components if len(comp) > 1]

    def _find_hotspots(self) -> list[dict[str, Any]]:
        """Find tables that would break the most objects if modified."""
        hotspots: list[dict[str, Any]] = []

        for table in self.tables:
            table_name = table.get("TABLE_NAME", "")
            if table_name not in self._graph:
                continue

            # Count SPs that reference this table
            predecessors = list(self._graph.predecessors(table_name))
            dependent_sps = [
                p for p in predecessors if self._graph.nodes[p].get("type") == "procedure"
            ]

            if dependent_sps:
                risk = (
                    "CRITICAL"
                    if len(dependent_sps) >= 20
                    else (
                        "HIGH"
                        if len(dependent_sps) >= 10
                        else ("MEDIUM" if len(dependent_sps) >= 5 else "LOW")
                    )
                )
                hotspots.append(
                    {
                        "table": table_name,
                        "dependent_sp_count": len(dependent_sps),
                        "dependent_sps": dependent_sps,
                        "risk_level": risk,
                    }
                )

        return sorted(hotspots, key=lambda x: x["dependent_sp_count"], reverse=True)

    def get_impact(self, table_name: str, analysis_result: dict[str, Any]) -> ImpactResult:
        """Calculate impact of modifying a specific table.

        Args:
            table_name: Name of the table to analyze.
            analysis_result: Result from analyze() method.

        Returns:
            ImpactResult with affected objects.
        """
        from sqlforensic import ImpactResult

        if table_name not in self._graph:
            return ImpactResult(table_name=table_name)

        predecessors = list(self._graph.predecessors(table_name))
        affected_sps = []
        affected_views = []
        affected_tables = []

        for pred in predecessors:
            node_type = self._graph.nodes[pred].get("type", "")
            if node_type == "procedure":
                affected_sps.append({"name": pred, "risk_level": "HIGH"})
            elif node_type == "view":
                affected_views.append(pred)
            elif node_type == "table":
                affected_tables.append(pred)

        # Also check tables connected via FK
        successors = list(self._graph.successors(table_name))
        for succ in successors:
            node_type = self._graph.nodes[succ].get("type", "")
            if node_type == "table" and succ not in affected_tables:
                affected_tables.append(succ)

        total = len(affected_sps) + len(affected_views) + len(affected_tables)
        risk_level = (
            "CRITICAL"
            if total >= 20
            else ("HIGH" if total >= 10 else ("MEDIUM" if total >= 5 else "LOW"))
        )

        return ImpactResult(
            table_name=table_name,
            affected_sps=affected_sps,
            affected_views=affected_views,
            affected_tables=affected_tables,
            risk_level=risk_level,
            total_affected=total,
        )
