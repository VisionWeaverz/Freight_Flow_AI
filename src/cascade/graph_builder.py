"""NetworkX graph builder representing port-carrier-warehouse supply chain dependencies."""

from __future__ import annotations
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
import networkx as nx

from src.common.schemas import CascadeNode, CascadeEdge


class SupplyChainGraphBuilder:
    """Constructs directed acyclic graphs representing supply chain schedules and physical handoffs."""

    def __init__(self):
        self.graph = nx.DiGraph()

    def build_graph(self, bookings: Optional[List[Dict[str, Any]]] = None) -> nx.DiGraph:
        """Populates nodes (ports, trucks, warehouses, deliveries) and temporal dependency edges."""
        G = nx.DiGraph()
        if not bookings:
            # Baseline mock pipeline for empty bookings call
            G.add_node("PORT_DEFAULT", node_type="PORT", name="Port Berth", status="ON_TIME")
            G.add_node("TRUCK_DEFAULT", node_type="TRUCK", name="Carrier Fleet", status="ON_TIME")
            G.add_node("WHS_DEFAULT", node_type="WAREHOUSE", name="Warehouse Intake", status="ON_TIME")
            G.add_node("CUST_DEFAULT", node_type="CUSTOMER", name="Customer SLA", status="ON_TIME")

            G.add_edge("PORT_DEFAULT", "TRUCK_DEFAULT", edge_type="BERTH_TO_TRUCK", delay_propagated_hours=0.0)
            G.add_edge("TRUCK_DEFAULT", "WHS_DEFAULT", edge_type="HIGHWAY_TRANSIT", delay_propagated_hours=0.0)
            G.add_edge("WHS_DEFAULT", "CUST_DEFAULT", edge_type="FINAL_MILE_FULFILLMENT", delay_propagated_hours=0.0)
            return G

        for b in bookings:
            source = b.get("source_id", "PORT")
            target = b.get("target_id", "TRUCK")
            G.add_node(source, **b.get("source_meta", {}))
            G.add_node(target, **b.get("target_meta", {}))
            G.add_edge(source, target, delay_propagated_hours=b.get("delay_hours", 0.0), edge_type=b.get("edge_type", "TRANSIT"))

        return G

    def build_from_cascade(self, nodes: List[CascadeNode], edges: List[CascadeEdge]) -> nx.DiGraph:
        """Constructs an nx.DiGraph from standardized CascadeNode and CascadeEdge objects."""
        G = nx.DiGraph()
        for node in nodes:
            G.add_node(node.node_id, **node.dict() if hasattr(node, "dict") else node.__dict__)
        for edge in edges:
            G.add_edge(edge.source, edge.target, **edge.dict() if hasattr(edge, "dict") else edge.__dict__)
        return G
