"""Cross-view prices must use the same scenario and applied pricing snapshot."""

from copy import deepcopy

import pytest

from tests.test_map_simulation import bundle
from src.common.schemas import DisruptionEvent, DisruptionType
from src.dashboard.components.scenario import evaluate_scenario
from src.dashboard.components.map_simulation import build_replay_payload, DISRUPTIONS, geography_for
from src.llm.explainer import LLMExplainer


@pytest.fixture(autouse=True)
def ensure_freightflow_db():
    # These tests pass isolated bundles; never seed or mutate the live database.
    yield


@pytest.mark.parametrize("shipment_id", ["SHP-1001", "SHP-1002", "SHP-1003", "SHP-1004", "SHP-1005"])
@pytest.mark.parametrize("disruption", DISRUPTIONS.values())
def test_prices_identical_for_every_view(bundle, shipment_id, disruption):
    bundle["shipment"]["shipment_id"] = shipment_id
    bundle["truck"]["driver_waiting_cost_per_hr"] = 750.25
    bundle["warehouse"]["overtime_cost_per_hr"] = 2400.35
    bundle["shipment"]["sla_penalty_per_hour_inr"] = 5000.45
    scenario = evaluate_scenario(shipment_id, disruption, 4, bundle=bundle)
    replay = build_replay_payload(bundle, disruption, 4, scenario=scenario)
    assert replay["risk"] == scenario["impact"].financial_risk_inr
    assert replay["risk"] == pytest.approx(sum(replay["penalties"].values()))
    for map_plan, agent_plan in zip(replay["plans"], scenario["plans"]):
        assert map_plan["cost"] == agent_plan.total_cost_inr
        assert map_plan["breakdown"] == agent_plan.cost_breakdown
        assert map_plan["cost"] == pytest.approx(sum(map_plan["breakdown"].values()))


def test_changed_rates_refresh_both_exposure_and_plans(bundle):
    before = evaluate_scenario("SHP-1005", "PORT_CONGESTION", 4, bundle=deepcopy(bundle))
    bundle["truck"]["driver_waiting_cost_per_hr"] = 750
    bundle["warehouse"].update(missed_slot_penalty_inr=18000, overtime_cost_per_hr=2400)
    bundle["shipment"]["sla_penalty_per_hour_inr"] = 5000
    after = evaluate_scenario("SHP-1005", "PORT_CONGESTION", 4, bundle=bundle)
    assert before["signature"] != after["signature"]
    assert before["impact"].financial_risk_inr == 17750
    # Driver 3h * 750 + missed slot 18000 + overtime 1.25h * 2400 + SLA .5h * 5000.
    assert after["impact"].financial_risk_inr == 25750
    assert [p.total_cost_inr for p in after["plans"]] == [6450, 16500, 7050]


def test_ai_comparison_never_fabricates_missing_prices(bundle):
    scenario = evaluate_scenario("SHP-1005", "PORT_CONGESTION", 4, bundle=bundle)
    event = DisruptionEvent(event_id="TEST", event_type=DisruptionType.PORT_CONGESTION,
        source_entity_id="SHP-1005", severity_level=.7, delay_hours=4, description="Test")
    explainer = LLMExplainer(api_key="")
    text = explainer._generate_structured_fallback_answer(event, scenario["plans"][0], "compare costs")
    assert "Not supplied" in text
    assert "8,200" not in text
    text = explainer._generate_structured_fallback_answer(event, scenario["plans"][0], "compare costs", scenario["plans"])
    for p in scenario["plans"]:
        assert f"₹{p.total_cost_inr:,.2f}" in text


def test_geography_is_not_hardcoded_to_jnpt():
    jnpt = geography_for("Nhava Sheva (JNPT)", "Bhiwandi Hub")
    mundra = geography_for("Mundra Port", "Ahmedabad Ring Hub")
    assert jnpt["port"] != mundra["port"]
    assert jnpt["warehouse"] != mundra["warehouse"]
