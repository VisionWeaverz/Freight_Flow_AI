"""Tests for cascade graph building and impact analysis."""

from src.cascade.graph_builder import SupplyChainGraphBuilder
from src.cascade.impact_analyzer import CascadeImpactAnalyzer
from src.common.schemas import DisruptionEvent, DisruptionType


def test_cascade_analyzer():
    builder = SupplyChainGraphBuilder()
    graph = builder.build_graph([])
    analyzer = CascadeImpactAnalyzer(graph)
    event = DisruptionEvent(
        event_id="EVT-01",
        event_type=DisruptionType.PORT_CONGESTION,
        source_entity_id="BERTH-1",
        severity_level=0.5,
        delay_hours=2.0,
        description="Berth delay test"
    )
    impact = analyzer.compute_impact(event)
    assert impact.disruption_event_id == "EVT-01"
    assert impact.downstream_delay_hours == 2.0
