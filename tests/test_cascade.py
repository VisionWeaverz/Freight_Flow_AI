"""Tests for cascade graph building and impact analysis."""

from src.cascade.graph_builder import SupplyChainGraphBuilder
from src.cascade.impact_analyzer import CascadeImpactAnalyzer, compute_cascade_impact
from src.common.schemas import DisruptionEvent, DisruptionType, CascadeImpact


def test_cascade_analyzer_disruption_event():
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


def test_compute_cascade_impact_shp_1005_four_hour_delay():
    """Unit test simulating 4-hour delay on SHP-1005."""
    impact = compute_cascade_impact("SHP-1005", added_delay_hours=4.0)

    assert isinstance(impact, CascadeImpact)
    assert impact.shipment_id == "SHP-1005"
    assert len(impact.nodes) == 4
    assert len(impact.edges) == 3

    # Check node lifecycle
    assert impact.nodes[0].node_type == "PORT"
    assert impact.nodes[0].status == "DELAYED"

    assert impact.nodes[1].node_type == "TRUCK"
    assert impact.nodes[1].status == "BREACHED"
    assert impact.nodes[1].details["waiting_penalty_inr"] == 1500.0

    assert impact.nodes[2].node_type == "WAREHOUSE"
    assert impact.nodes[2].status == "BREACHED"
    assert impact.nodes[2].details["slot_missed"] is True
    assert impact.nodes[2].details["missed_slot_penalty_inr"] == 12500.0

    assert impact.nodes[3].node_type == "CUSTOMER"
    assert impact.nodes[3].status == "BREACHED"
    assert impact.nodes[3].details["sla_breached"] is True

    # Financial Exposure
    assert impact.financial_risk_inr == 17750.0
    assert impact.risk_level == "CRITICAL"


def test_compute_cascade_impact_zero_delay():
    """Unit test for on-time operations without penalty."""
    impact = compute_cascade_impact("SHP-1005", added_delay_hours=0.0)
    assert impact.financial_risk_inr == 0.0
    assert impact.risk_level == "LOW"
    assert impact.nodes[0].status == "ON_TIME"
    assert impact.nodes[1].status == "ON_TIME"


def test_compute_cascade_impact_truck_breakdown_shp_1001():
    """Unit test for truck breakdown disruption: port stays on time, truck and downstream delay."""
    impact = compute_cascade_impact("SHP-1001", added_delay_hours=3.5, disruption_type="TRUCK_BREAKDOWN")
    assert impact.nodes[0].node_type == "PORT"
    assert impact.nodes[0].status == "ON_TIME"
    assert impact.nodes[0].delay_hours == 0.0

    assert impact.nodes[1].node_type == "TRUCK"
    assert impact.nodes[1].status in ("BREACHED", "DELAYED")
    assert impact.nodes[1].delay_hours == 3.5

    assert impact.nodes[2].node_type == "WAREHOUSE"
    assert impact.nodes[3].node_type == "CUSTOMER"
    assert impact.nodes[3].status == "BREACHED"
    assert impact.nodes[3].details["sla_breached"] is True
    assert impact.financial_risk_inr > 0


def test_compute_cascade_impact_warehouse_bottleneck_shp_1001():
    """Unit test for warehouse dock bottleneck: port and truck stay on time, dock and customer delay."""
    impact = compute_cascade_impact("SHP-1001", added_delay_hours=4.0, disruption_type="WAREHOUSE_BOTTLENECK")
    assert impact.nodes[0].status == "ON_TIME"
    assert impact.nodes[0].delay_hours == 0.0

    assert impact.nodes[1].status == "ON_TIME"
    assert impact.nodes[1].delay_hours == 0.0

    assert impact.nodes[2].node_type == "WAREHOUSE"
    assert impact.nodes[2].status == "BREACHED"
    assert impact.nodes[2].delay_hours == 4.0

    assert impact.nodes[3].node_type == "CUSTOMER"
    assert impact.nodes[3].status == "BREACHED"
    assert impact.nodes[3].details["sla_breached"] is True
    assert impact.financial_risk_inr > 0
