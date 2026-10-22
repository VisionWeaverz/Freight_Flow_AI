"""LLM client integration to translate disruptions into events and explain recovery plans."""

from src.common.schemas import RecoveryPlan, DisruptionEvent
from src.llm.prompts import PLAN_EXPLANATION_PROMPT, TEXT_TO_EVENT_PROMPT
from src.common.config import GEMINI_API_KEY, LLM_PROVIDER


class LLMExplainer:
    """Provides human-readable justifications for negotiated recovery plans."""

    def __init__(self, api_key: str = GEMINI_API_KEY):
        self.api_key = api_key

    def explain_plan(self, disruption: DisruptionEvent, plan: RecoveryPlan) -> str:
        """Calls LLM API to provide plain-text explanation of the chosen recovery plan."""
        # TODO: Integrate google-generativeai / OpenAI API call
        return (
            f"Plan '{plan.category.value}' mitigates the {disruption.description} "
            f"by realigning the trucking appointment with Port Berth Window {plan.port_slot_id}, "
            f"saving estimated idle driver hours while containing costs to ₹{plan.total_cost_inr:,.2f}."
        )

    def parse_text_event(self, text: str) -> dict:
        """Extracts structured disruption signals from unstructured text/emails."""
        # TODO: Implement LLM text-to-event parser
        return {
            "event_type": "PORT_CONGESTION",
            "source_entity_id": "PORT_BERTH_2",
            "delay_hours": 3.0,
            "severity_level": 0.6,
            "description": text
        }
