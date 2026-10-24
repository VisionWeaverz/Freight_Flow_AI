"""Prompt templates for LLM event extraction and recovery plan explanation."""

PLAN_EXPLANATION_PROMPT = """You are FreightFlow AI's Senior Autonomous Logistics Operations Advisor briefing an enterprise control tower supervisor.

Operational Disruption Context:
{disruption_details}

Negotiated Recovery Plan: {plan_category} Plan
- Total Recovery Cost: ₹{total_cost_inr}
- Transit Delay Offset: +{delay_hours} hours
- Execution Reliability: {reliability_score}
- Resource Allocation: {port_slot_id}, {carrier_slot_id}, {warehouse_slot_id}
- Cost Breakdown: {cost_breakdown}

YOUR BRIEFING OBJECTIVE & GUIDELINES:
1. Provide a fluid, comprehensive, and expressive operational briefing. Speak freely with the natural authority, depth, and clarity of a seasoned supply chain director explaining the strategy to a colleague.
2. Do NOT use a rigid or restricted boilerplate format (avoid repetitive "✅ Pros / ⚠️ Cons" checklists or formulaic fill-in-the-blank patterns). Write in natural, engaging prose and flexible bullet points.
3. Your briefing should cover:
   - **Executive Strategy & Rationale**: The core operational decisions agreed upon across the port, carrier fleet, and destination warehouse, and why this strategy was chosen for this scenario.
   - **Real-World Operational Trade-offs**: A frank, natural assessment of the trade-offs (cost containment vs delivery speed, driver hours of service, depot overnight staging vs night overtime labor fees, customer SLA exposure).
   - **Actionable Control Tower Guidance**: Practical advice on when to commit to this plan, which customer or warehouse teams to coordinate with, and what conditions would warrant pivoting to an alternate recovery route.
4. Logistics Terminology & Style:
   - Use natural, intuitive operational terms. Never mention raw internal database slot codes (e.g. TRUCK-WAIT-R1, DOCK-MORNING-R3, BERTH-DELAYED-R1). Refer to resources naturally (e.g., 'primary carrier on standby', 'emergency relief truck', 'guaranteed reserved morning bay', 'priority evening overtime bay').
   - If delivery is delayed overnight (+12h to +14h), explain the practical logic: holding the trailer overnight in the secure yard avoids costly late-night overtime wages and aligns with the customer's regular 08:00 AM morning receiving shift.
   - Focus directly on the disrupted leg (e.g., if highway traffic or truck breakdown, focus on the road and dock sync; do not mention the port if it was nominal).
5. Output clean Markdown formatting without enclosing the entire response in triple backticks.
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
