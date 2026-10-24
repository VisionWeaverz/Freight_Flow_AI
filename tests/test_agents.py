"""Tests for autonomous agents and central coordinator negotiation logic."""

import pytest
from datetime import datetime
from src.agents.coordinator import (
    CentralCoordinator,
    is_pareto_dominated,
    compute_pareto_frontier,
)
from src.cascade.impact_analyzer import compute_cascade_impact
from src.orchestrator import FreightFlowOrchestrator
from src.llm.explainer import LLMExplainer
from src.common.schemas import (
    DisruptionEvent,
    DisruptionType,
    CascadeImpact,
    CascadeNode,
    PlanCategory,
)


def test_coordinator_negotiation_legacy_interface():
    """Tests the legacy coordinate_recovery() wrapper against real agent offers."""
    coordinator = CentralCoordinator(max_rounds=3)
    event = DisruptionEvent(
        event_id="EVT-02",
        event_type=DisruptionType.TRUCK_BREAKDOWN,
        source_entity_id="TRUCK-01",
        severity_level=0.8,
        delay_hours=3.0,
        description="Engine failure test",
    )
    plans, feasible = coordinator.coordinate_recovery(event)
    assert feasible is True
    assert len(plans) == 3

    categories = {p.category for p in plans}
    assert categories == {
        PlanCategory.CHEAPEST,
        PlanCategory.FASTEST,
        PlanCategory.SAFEST,
    }

    # Verify not dummy constants (dummy total was 9200, 13500, 10800)
    for p in plans:
        assert p.carrier_slot_id.startswith("TRUCK-")
        assert p.port_slot_id.startswith("BERTH-")
        assert p.warehouse_slot_id.startswith("DOCK-")
        assert p.total_cost_inr > 0
        assert p.negotiation_rounds_taken == 3
        # Cost breakdown integrity
        expected_total = round(
            p.cost_breakdown["port"]
            + p.cost_breakdown["carrier"]
            + p.cost_breakdown["warehouse"],
            2,
        )
        assert p.total_cost_inr == expected_total


def test_coordinator_run_recovery_negotiation_shp_1005():
    """Tests run_recovery_negotiation() using the benchmark SHP-1005 4h delay impact."""
    impact = compute_cascade_impact("SHP-1005", added_delay_hours=4.0)
    coordinator = CentralCoordinator(max_rounds=3)

    plans = coordinator.run_recovery_negotiation(impact)
    assert len(plans) == 3

    cheap_plan = next(p for p in plans if p.category == PlanCategory.CHEAPEST)
    fast_plan = next(p for p in plans if p.category == PlanCategory.FASTEST)
    safe_plan = next(p for p in plans if p.category == PlanCategory.SAFEST)

    # 1. Cheapest must have lowest cost
    assert cheap_plan.total_cost_inr <= fast_plan.total_cost_inr
    assert cheap_plan.total_cost_inr <= safe_plan.total_cost_inr

    # 2. Fastest must have lowest delay
    assert fast_plan.total_delay_hours <= cheap_plan.total_delay_hours
    assert fast_plan.total_delay_hours <= safe_plan.total_delay_hours

    # 3. Safest must have highest reliability
    assert safe_plan.reliability_score >= cheap_plan.reliability_score
    assert safe_plan.reliability_score >= fast_plan.reliability_score

    # 4. Slot choices reflect specific optimization goals
    # Fastest chooses replacement truck (0 waiting delay)
    assert "REPLACEMENT" in fast_plan.carrier_slot_id
    # Safest chooses morning warehouse intake (0.97 reliability)
    assert "MORNING" in safe_plan.warehouse_slot_id


def test_coordinator_pareto_dominance_verification():
    """Verifies that the generated plans are on the non-dominated Pareto frontier."""
    impact = compute_cascade_impact("SHP-1005", added_delay_hours=4.0)
    coordinator = CentralCoordinator(max_rounds=3)

    plans = coordinator.run_recovery_negotiation(impact)

    # All returned plans must not be dominated by any other returned plan
    for plan in plans:
        assert not is_pareto_dominated(plan, plans)


def test_coordinator_three_negotiation_rounds_different_offers():
    """Verifies that all 3 rounds generate distinct, adapted counteroffers."""
    coordinator = CentralCoordinator(max_rounds=3)
    ref_time = datetime(2026, 10, 23, 14, 0, 0)

    # Round 1: Autonomous baseline (cheaper option)
    p_r1 = coordinator.port_agent.generate_initial_offer(
        1, {"delay_hours": 4.0, "reference_time": ref_time}
    )
    c_r1 = coordinator.carrier_agent.generate_initial_offer(
        1, {"delay_hours": 4.0, "reference_time": ref_time}
    )
    w_r1 = coordinator.warehouse_agent.generate_initial_offer(
        1, {"delay_hours": 4.0, "reference_time": ref_time}
    )

    # Round 2: Speed and reliability pressure
    p_r2 = coordinator.port_agent.generate_counter_offer(
        2, {"delay_hours": 4.0, "prefer_fast": True, "prefer_cheap": False, "reference_time": ref_time}
    )
    c_r2 = coordinator.carrier_agent.generate_counter_offer(
        2, {"delay_hours": 4.0, "prefer_fast": True, "reference_time": ref_time}
    )
    w_r2 = coordinator.warehouse_agent.generate_counter_offer(
        2, {"delay_hours": 4.0, "prefer_reliable": True, "reference_time": ref_time}
    )

    # Round 3: Cost-containment pressure
    p_r3 = coordinator.port_agent.generate_counter_offer(
        3, {"delay_hours": 4.0, "prefer_cheap": True, "reference_time": ref_time}
    )
    c_r3 = coordinator.carrier_agent.generate_counter_offer(
        3, {"delay_hours": 4.0, "prefer_fast": False, "reference_time": ref_time}
    )

    # Assert Round 1 vs Round 2 differences
    assert "DELAYED" in p_r1.slot_id
    assert "EXPEDITED" in p_r2.slot_id
    assert p_r2.cost_inr > p_r1.cost_inr

    assert "REPLACEMENT" in c_r2.slot_id
    assert "MORNING" in w_r2.slot_id

    # Assert Round 3 cost-containment pivots back to lower-cost options
    assert "DELAYED" in p_r3.slot_id
    assert p_r3.cost_inr < p_r2.cost_inr


def test_coordinator_zero_delay_deterministic():
    """Verifies that a 0-hour delay scenario is handled gracefully and deterministically."""
    impact = compute_cascade_impact("SHP-1005", added_delay_hours=0.0)
    coordinator = CentralCoordinator(max_rounds=3)

    plans = coordinator.run_recovery_negotiation(impact)
    assert len(plans) == 3

    for p in plans:
        assert p.is_feasible is True
        assert p.total_cost_inr >= 1200.0  # Base berth fee minimum
        assert p.reliability_score > 0.0


def test_coordinator_invalid_impact_raises():
    """Verifies that invalid or negative impacts raise ValueError explicitly."""
    coordinator = CentralCoordinator(max_rounds=3)

    with pytest.raises(ValueError, match="'impact' is required"):
        coordinator.run_recovery_negotiation(None)

    bad_impact = CascadeImpact(
        disruption_event_id="EVT-BAD",
        initial_delay_hours=-2.0,
        downstream_delay_hours=-2.0,
    )
    with pytest.raises(ValueError, match="delay must be >= 0"):
        coordinator.run_recovery_negotiation(bad_impact)


def test_orchestrator_pipeline_end_to_end():
    """Tests the full orchestrator pipeline with real cascade impact and coordinator."""
    orchestrator = FreightFlowOrchestrator()
    orchestrator.llm_explainer = LLMExplainer(api_key="")  # Use deterministic heuristic fallback for tests
    disruption = DisruptionEvent(
        event_id="EVT-JNPT-TEST",
        event_type=DisruptionType.PORT_CONGESTION,
        source_entity_id="SHP-1005",
        severity_level=0.75,
        delay_hours=4.0,
        description="4-hour port congestion test on SHP-1005",
    )

    result = orchestrator.handle_disruption_pipeline(disruption)
    assert result["is_feasible"] is True
    assert len(result["plans"]) == 3
    assert result["cascade_impact"].total_financial_risk_inr == 17750.0

    for plan in result["plans"]:
        assert plan.llm_explanation is not None
        assert len(plan.llm_explanation) > 10


def test_orchestrator_invalid_shipment_raises():
    """Verifies that non-existent SHP-* IDs raise ValueError explicitly rather than fabricating plans."""
    orchestrator = FreightFlowOrchestrator()
    fake_disruption = DisruptionEvent(
        event_id="EVT-FAKE",
        event_type=DisruptionType.PORT_CONGESTION,
        source_entity_id="SHP-NONEXISTENT-9999",
        severity_level=0.5,
        delay_hours=3.0,
        description="Querying an unseeded shipment",
    )

    with pytest.raises(ValueError, match="not found in database"):
        orchestrator.handle_disruption_pipeline(fake_disruption)


def test_orchestrator_negative_delay_raises():
    """Verifies that negative delay hours raise ValueError in orchestrator."""
    orchestrator = FreightFlowOrchestrator()
    bad_disruption = DisruptionEvent(
        event_id="EVT-NEG",
        event_type=DisruptionType.PORT_CONGESTION,
        source_entity_id="SHP-1005",
        severity_level=0.5,
        delay_hours=-1.0,
        description="Negative delay test",
    )

    with pytest.raises(ValueError, match="delay_hours must be >= 0"):
        orchestrator.handle_disruption_pipeline(bad_disruption)
