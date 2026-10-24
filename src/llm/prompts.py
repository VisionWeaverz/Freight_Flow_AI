"""Prompt templates for LLM event extraction and recovery plan explanation."""

PLAN_EXPLANATION_PROMPT = """You are FreightFlow AI's Senior Operational Recovery Advisor.
Provide a concise, focused executive rationale for the selected recovery plan.
Keep it short, on-point, and structured with bullet points. Do NOT write long essays or walls of text.
Do NOT wrap the output in markdown code blocks (no backticks).

Disruption Context:
{disruption_details}

Selected Recovery Plan: {plan_category} Plan
- Total Recovery Cost: ₹{total_cost_inr}
- Transit Delay Offset: +{delay_hours} hours
- Execution Reliability: {reliability_score}
- Resource Allocation: Port {port_slot_id}, Carrier {carrier_slot_id}, Warehouse Dock {warehouse_slot_id}
- Cost Breakdown: {cost_breakdown}

Format your output EXACTLY as follows:

#### 🎯 Why {plan_category} Plan & Decision Rationale
- **Decision Taken**: 1-2 sentences explaining how the multi-agent decision directly resolved the active disruption at its source (e.g., if highway traffic or truck breakdown, focus on carrier rerouting/replacement fleet and warehouse intake sync; if warehouse dock bottleneck, focus on dock overtime vs morning bay; if port/vessel delay, focus on berth crane and gate sync). Do NOT mention port delays if the port was nominal and cleared on time.
- **Why Choose This**: 1-2 sentences on the exact operational/contractual conditions when the supervisor should choose this plan.

#### ✅ Pros
- 2-3 concise, high-impact bullet points highlighting key benefits (e.g. cost savings, delay mitigation, or reliability certainty).

#### ⚠️ Cons
- 2 concise bullet points highlighting key trade-offs or operational risks (e.g. added delay, carrier premium, or schedule flexibility requirements).
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
