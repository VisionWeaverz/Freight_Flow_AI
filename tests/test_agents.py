"""Tests for autonomous agents and coordinator negotiation logic."""

from src.agents.coordinator import CentralCoordinator
from src.common.schemas import DisruptionEvent, DisruptionType


def test_coordinator_negotiation():
    coordinator = CentralCoordinator(max_rounds=3)
    event = DisruptionEvent(
        event_id="EVT-02",
        event_type=DisruptionType.TRUCK_BREAKDOWN,
        source_entity_id="TRUCK-01",
        severity_level=0.8,
        delay_hours=3.0,
        description="Engine failure test"
    )
    plans, feasible = coordinator.coordinate_recovery(event)
    assert feasible is True
    assert len(plans) == 3
