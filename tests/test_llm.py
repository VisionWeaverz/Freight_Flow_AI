"""Unit and integration tests for LLMExplainer and Gemini integration."""

import pytest
from unittest.mock import patch, MagicMock
from src.llm.explainer import LLMExplainer
from src.common.schemas import DisruptionEvent, RecoveryPlan, DisruptionType, PlanCategory


@pytest.fixture
def sample_disruption():
    return DisruptionEvent(
        event_id="EVT-TEST-001",
        event_type=DisruptionType.PORT_CONGESTION,
        source_entity_id="SHP-1005",
        severity_level=0.75,
        delay_hours=4.0,
        description="JNPT Berth Congestion (+4.0 hrs)"
    )


@pytest.fixture
def sample_plan():
    return RecoveryPlan(
        plan_id="PLAN-TEST-001",
        category=PlanCategory.CHEAPEST,
        carrier_slot_id="TRUCK-SLOT-01",
        port_slot_id="BERTH-SLOT-01",
        warehouse_slot_id="DOCK-SLOT-02",
        total_cost_inr=6200.0,
        total_delay_hours=14.0,
        reliability_score=0.82,
        cost_breakdown={"port": 1200.0, "carrier": 3000.0, "warehouse": 2000.0},
        negotiation_rounds_taken=3,
        is_feasible=True,
    )


def test_explainer_initialization_no_key():
    explainer = LLMExplainer(api_key="")
    assert not explainer.is_configured()
    assert "flash" in explainer.model


def test_explainer_initialization_with_key():
    explainer = LLMExplainer(api_key="AIzaSyDummyTestKey12345", model="gemini-2.0-flash")
    assert explainer.is_configured()
    assert explainer.model == "gemini-2.0-flash"


def test_heuristic_explanation_fallback(sample_disruption, sample_plan):
    explainer = LLMExplainer(api_key="")
    explanation = explainer.explain_plan(sample_disruption, sample_plan)
    assert explainer.last_source == "heuristic"
    assert "₹6,200.00" in explanation
    assert "Cheapest Plan Analysis" in explanation


def test_heuristic_explanation_all_categories(sample_disruption, sample_plan):
    explainer = LLMExplainer(api_key="")

    for cat in [PlanCategory.CHEAPEST, PlanCategory.FASTEST, PlanCategory.SAFEST]:
        sample_plan.category = cat
        exp = explainer.explain_plan(sample_disruption, sample_plan)
        assert len(exp) > 50
        assert sample_plan.category.value.lower() in exp.lower()


def test_custom_question_fallback(sample_disruption, sample_plan):
    explainer = LLMExplainer(api_key="")
    answer = explainer.ask_custom_question(sample_disruption, sample_plan, "What about driver idle cost?")
    assert "Live Gemini API key not configured" in answer
    assert "₹6,200.00" in answer


def test_text_to_event_heuristic_fallback():
    explainer = LLMExplainer(api_key="")
    res = explainer.parse_text_event("Driver reported truck engine breakdown delay of 3.5 hours on highway")
    assert res["event_type"] == DisruptionType.TRUCK_BREAKDOWN.value
    assert res["delay_hours"] == 3.5


def test_connection_test_invalid_key():
    explainer = LLMExplainer()
    success, msg = explainer.test_connection(api_key="invalid_test_key_xyz")
    assert not success
    assert "failed" in msg.lower() or "error" in msg.lower() or "not valid" in msg.lower()


def test_mock_live_gemini_call(sample_disruption, sample_plan):
    explainer = LLMExplainer(api_key="AIzaSyMockedValidKey123")
    mock_text = "Mocked Gemini Rationale: This plan achieves optimal cost containment."

    with patch.object(explainer, "_call_gemini_raw", return_value=mock_text):
        explanation = explainer.explain_plan(sample_disruption, sample_plan)
        assert explainer.last_source == "gemini"
        assert "Mocked Gemini Rationale" in explanation
