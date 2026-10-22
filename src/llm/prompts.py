"""Prompt templates for LLM event extraction and recovery plan explanation."""

PLAN_EXPLANATION_PROMPT = """
You are FreightFlow AI's Recovery Explainer. 
Explain the chosen recovery plan in concise, professional terms for human logistics supervisors.

Disruption Event:
{disruption_details}

Selected Recovery Plan ({plan_category}):
- Total Cost: ₹{total_cost_inr}
- Expected Delay: {delay_hours} hours
- Reliability Score: {reliability_score}
- Cost Breakdown: {cost_breakdown}

Explain:
1. Why this plan is optimal for this operational scenario.
2. The trade-offs made between port berth availability, trucking wait times, and warehouse bay slots.
3. Recommended next action for the logistics operator.
"""

TEXT_TO_EVENT_PROMPT = """
Convert the following unstructured logistics delay update into a structured JSON event:
Text: "{raw_text}"

Return JSON matching:
{
  "event_type": "PORT_CONGESTION | VESSEL_DELAY | TRUCK_BREAKDOWN | TRAFFIC_INCIDENT | WAREHOUSE_BOTTLENECK",
  "source_entity_id": "string",
  "delay_hours": float,
  "severity_level": float (0.0 to 1.0),
  "description": "concise summary"
}
"""
