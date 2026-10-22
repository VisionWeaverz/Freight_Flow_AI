"""Downstream impact propagation and financial risk calculation (INR at risk)."""

from __future__ import annotations
try:
    import networkx as nx
except ImportError:
    nx = None

from src.common.schemas import DisruptionEvent, CascadeImpact


class CascadeImpactAnalyzer:
    """Traverses downstream graph to compute affected bookings and monetary loss."""

    def __init__(self, graph=None):
        self.graph = graph

    def compute_impact(self, disruption: DisruptionEvent) -> CascadeImpact:
        """Calculates downstream nodes affected and accumulates total INR at risk."""
        # TODO: BFS / DFS traversal from source node of disruption
        return CascadeImpact(
            disruption_event_id=disruption.event_id,
            affected_nodes=[],
            affected_booking_ids=[],
            total_financial_risk_inr=0.0,
            downstream_delay_hours=disruption.delay_hours,
            critical_path=[]
        )
