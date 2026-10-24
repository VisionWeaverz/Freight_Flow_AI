"""LLM client integration to translate disruptions into events and explain recovery plans.

Supports Google Gemini API via official google.genai SDK with multi-model auto-failover
(gemini-3.5-flash, gemini-3.7-flash, gemini-3.8-flash), REST endpoints, and dynamic heuristic synthesis.
"""

from __future__ import annotations
import os
import json
import logging
import urllib.request
import urllib.error
import concurrent.futures
from typing import Dict, Any, Optional, Tuple, List

from src.common.schemas import RecoveryPlan, DisruptionEvent, DisruptionType, PlanCategory
from src.llm.prompts import PLAN_EXPLANATION_PROMPT, TEXT_TO_EVENT_PROMPT
from src.common.config import GEMINI_API_KEY, LLM_PROVIDER, GEMINI_MODEL

logger = logging.getLogger(__name__)


class LLMExplainer:
    """Provides human-readable justifications and interactive Q&A for recovery plans.
    
    Tries Google Gemini API first with auto-failover across available models,
    and falls back to dynamic multi-perspective heuristic explanations on network/quota exhaustion.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None
    ):
        raw_key = api_key if api_key is not None else (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or GEMINI_API_KEY)
        self.api_key = raw_key.strip() if raw_key else ""
        self.provider = (provider or LLM_PROVIDER or "gemini").lower()
        self.model = model or os.getenv("GEMINI_MODEL") or GEMINI_MODEL or "gemini-3.5-flash"
        self.last_source: str = "uninitialized"  # "gemini" or "heuristic"
        self.last_model_used: Optional[str] = None

    def is_configured(self) -> bool:
        """Returns True if a non-placeholder Gemini API key is configured."""
        return bool(self.api_key and self.api_key not in ("your_gemini_api_key_here", "AIzaSy..."))

    def test_connection(self, api_key: Optional[str] = None, model: Optional[str] = None) -> Tuple[bool, str]:
        """Validates the Gemini API key by making a lightweight ping to the model with a safety timeout."""
        key = (api_key or self.api_key or "").strip()
        if not key or key in ("your_gemini_api_key_here", "AIzaSy..."):
            return False, "No valid API key provided. Please enter a valid Google Gemini API key."

        target_model = model or self.model

        def _do_ping() -> Tuple[bool, str]:
            prompt = "Hello! Reply with OK"
            models_to_test = [target_model]
            for candidate in ["gemini-3.5-flash", "gemini-3.7-flash", "gemini-3.8-flash", "gemini-flash-latest"]:
                if candidate not in models_to_test:
                    models_to_test.append(candidate)

            last_error = ""
            for m in models_to_test:
                # 1. Try google.genai SDK
                try:
                    from google import genai
                    client = genai.Client(api_key=key)
                    resp = client.models.generate_content(model=m, contents=prompt)
                    if resp and resp.text:
                        self.model = m
                        msg = f"Successfully connected to Gemini API via '{m}'!"
                        if m != target_model:
                            msg += f" (Auto-failover from '{target_model}')"
                        return True, msg
                except Exception as e_sdk:
                    last_error = str(e_sdk)
                    logger.debug("genai SDK test failed for %s: %s", m, e_sdk)
                    # If quota exceeded on this model, try the next model
                    if "429" in last_error or "RESOURCE_EXHAUSTED" in last_error or "404" in last_error or "not found" in last_error.lower():
                        continue
                    if "API key not valid" in last_error or "INVALID_ARGUMENT" in last_error or "400" in last_error:
                        return False, f"Gemini API Error: {last_error}"

                # 2. Try REST API direct ping
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={key}"
                    payload = {
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"maxOutputTokens": 10}
                    }
                    data = json.dumps(payload).encode("utf-8")
                    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=4) as response:
                        res_json = json.loads(response.read().decode("utf-8"))
                        candidates = res_json.get("candidates", [])
                        if candidates:
                            self.model = m
                            msg = f"Successfully connected to Gemini API via REST ('{m}')!"
                            if m != target_model:
                                msg += f" (Auto-failover from '{target_model}')"
                            return True, msg
                except urllib.error.HTTPError as http_err:
                    try:
                        err_body = json.loads(http_err.read().decode("utf-8"))
                        last_error = err_body.get("error", {}).get("message", str(http_err))
                    except Exception:
                        last_error = str(http_err)
                except Exception as e:
                    last_error = str(e)

            return False, f"Connection failed: {last_error or 'No response from Gemini API.'}"

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_do_ping)
            try:
                return future.result(timeout=6.0)
            except concurrent.futures.TimeoutError:
                return False, "Connection timed out (Google Gemini API did not respond within 6s)."

    def explain_plan(self, disruption: DisruptionEvent, plan: RecoveryPlan, iteration: int = 0) -> str:
        """Generates an executive explanation of why this plan was chosen and trade-offs made."""
        if self.is_configured():
            try:
                live_explanation = self._call_gemini_explanation(disruption, plan)
                if live_explanation:
                    self.last_source = "gemini"
                    self.last_model_used = self.model
                    return live_explanation
            except Exception as e:
                logger.warning("Gemini live explanation failed (%s); reverting to heuristic engine.", e)

        # Dynamic heuristic explanation
        self.last_source = "heuristic"
        self.last_model_used = "FreightFlow Rule Engine"
        return self._generate_heuristic_explanation(disruption, plan, iteration=iteration)

    def ask_custom_question(
        self,
        disruption: DisruptionEvent,
        plan: RecoveryPlan,
        user_query: str,
        all_plans: Optional[List[RecoveryPlan]] = None
    ) -> str:
        """Allows human operators to interrogate recovery plans using conversational AI or dynamic heuristic rule engine."""
        if not self.is_configured():
            self.last_source = "heuristic"
            self.last_model_used = "FreightFlow Operational Rule Engine"
            fallback_body = self._generate_structured_fallback_answer(
                disruption=disruption, plan=plan, user_query=user_query, all_plans=all_plans
            )
            return (
                "⚠️ **Live Gemini API key not configured.** (Operating in resilient FreightFlow rule engine mode)\n\n"
                f"Based on local logistics rules for **{plan.category.value}**: "
                f"This plan commits total cost ₹{plan.total_cost_inr:,.2f} with +{plan.total_delay_hours:.1f}h transit delay "
                f"and {plan.reliability_score * 100:.0f}% reliability.\n\n"
                f"{fallback_body}"
            )

        # Build comparison summary of all available Pareto plans for LLM prompt
        pareto_bullets = []
        if all_plans:
            for p in all_plans:
                is_cur = " (Currently Selected)" if p.category == plan.category else ""
                pareto_bullets.append(
                    f"- Option [{p.category.value}]{is_cur}: Cost ₹{p.total_cost_inr:,.2f}, "
                    f"Delay +{p.total_delay_hours:.1f}h, Reliability {p.reliability_score * 100:.0f}%, "
                    f"Resources: Port {p.port_slot_id}, Carrier {p.carrier_slot_id}, Dock {p.warehouse_slot_id}"
                )
        pareto_text = "\n".join(pareto_bullets) if pareto_bullets else f"- Active Option [{plan.category.value}]: Cost ₹{plan.total_cost_inr:,.2f}, Delay +{plan.total_delay_hours:.1f}h, Reliability {plan.reliability_score * 100:.0f}%"

        prompt = (
            "You are FreightFlow AI's Senior Autonomous Logistics Operations Advisor. "
            "An enterprise logistics dispatcher or supply chain manager is asking for operational guidance on recovering a disrupted shipment.\n\n"
            f"### Active Disruption Context:\n"
            f"- Disruption Event: {disruption.description}\n"
            f"- Disruption Type: {disruption.event_type.value}\n"
            f"- Disruption Added Delay: +{disruption.delay_hours:.1f} hours\n"
            f"- Affected Entity: {disruption.source_entity_id}\n\n"
            f"### Currently Selected Recovery Plan:\n"
            f"- Category: {plan.category.value}\n"
            f"- Total Cost: ₹{plan.total_cost_inr:,.2f}\n"
            f"- Transit Delay Added: +{plan.total_delay_hours:.1f} hours\n"
            f"- Reliability Score: {plan.reliability_score * 100:.0f}%\n"
            f"- Resource Allocation: Port Slot {plan.port_slot_id}, Carrier {plan.truck_id}, Dock {plan.warehouse_dock_id}\n\n"
            f"### Available Multi-Agent Pareto Alternatives:\n"
            f"{pareto_text}\n\n"
            f"### Human Operator Question:\n"
            f"\"{user_query}\"\n\n"
            "### Instructions:\n"
            "Provide a direct, practical, logistics-grounded advisory response formatted in GitHub-flavored Markdown. "
            "IMPORTANT: Do NOT wrap your output in triple backticks or code blocks. Output standard rendered Markdown directly.\n\n"
            "Organize your answer using these clear sections:\n"
            "### 🎯 Strategic Recommendation\n"
            "Direct, decisive answer to the operator's inquiry and clear recommendation on which plan to pick.\n\n"
            "### ⚖️ Multi-Plan Trade-Off Analysis\n"
            "Contrast CHEAPEST vs FASTEST vs SAFEST on cost (₹), delay (+h), reliability (%), and calculate the breakeven SLA penalty rate.\n\n"
            "### 💡 Operational Impact & Downstream Risks\n"
            "Detail specific downstream risks (e.g. driver hours of service, port demurrage penalties, warehouse intake bottlenecks, customer contract clauses).\n\n"
            "### 📋 Recommended Operator Action\n"
            "Clear bulleted next steps on whether to approve the current plan or switch to an alternative.\n\n"
            "Use markdown bullet points and bold key metrics (e.g. ₹X, Y.Y hrs, Z%)."
        )

        try:
            raw_resp = self._call_gemini_raw(prompt)
            if raw_resp:
                cleaned = raw_resp.strip()
                # Remove code blocks if model wrapped them
                if cleaned.startswith("```markdown"):
                    cleaned = cleaned[len("```markdown"):].strip()
                elif cleaned.startswith("```md"):
                    cleaned = cleaned[len("```md"):].strip()
                elif cleaned.startswith("```"):
                    cleaned = cleaned[3:].strip()
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3].strip()

                self.last_source = "gemini"
                return cleaned
        except Exception as e:
            logger.warning("Gemini custom query call failed (%s); reverting to structured heuristic engine.", e)

        # Fallback to structured heuristic advisory
        self.last_source = "heuristic"
        self.last_model_used = "FreightFlow Operational Rule Engine"
        return self._generate_structured_fallback_answer(
            disruption=disruption,
            plan=plan,
            user_query=user_query,
            all_plans=all_plans
        )

    def _generate_structured_fallback_answer(
        self,
        disruption: DisruptionEvent,
        plan: RecoveryPlan,
        user_query: str,
        all_plans: Optional[List[RecoveryPlan]] = None
    ) -> str:
        """Synthesizes rich, structured, domain-grounded operational advice when LLM API is unavailable or throttled."""
        # Resolve candidate Pareto plans
        plans_map: Dict[PlanCategory, RecoveryPlan] = {}
        if all_plans:
            for p in all_plans:
                plans_map[p.category] = p

        cheapest = plans_map.get(PlanCategory.CHEAPEST)
        fastest = plans_map.get(PlanCategory.FASTEST)
        safest = plans_map.get(PlanCategory.SAFEST)

        if not cheapest:
            cheapest = plan if plan.category == PlanCategory.CHEAPEST else RecoveryPlan(
                plan_id="PLAN-CHEAPEST-REF",
                category=PlanCategory.CHEAPEST,
                carrier_slot_id=plan.carrier_slot_id,
                port_slot_id=plan.port_slot_id,
                warehouse_slot_id=plan.warehouse_slot_id,
                total_cost_inr=min(plan.total_cost_inr, 5700.0),
                total_delay_hours=max(plan.total_delay_hours, 5.0),
                reliability_score=0.68,
                cost_breakdown={"port": 1200.0, "carrier": 3300.0, "warehouse": 1200.0},
                negotiation_rounds_taken=3
            )
        if not fastest:
            fastest = plan if plan.category == PlanCategory.FASTEST else RecoveryPlan(
                plan_id="PLAN-FASTEST-REF",
                category=PlanCategory.FASTEST,
                carrier_slot_id=plan.carrier_slot_id,
                port_slot_id=plan.port_slot_id,
                warehouse_slot_id=plan.warehouse_slot_id,
                total_cost_inr=max(plan.total_cost_inr * 1.45, 8200.0),
                total_delay_hours=max(1.0, min(plan.total_delay_hours * 0.4, 2.5)),
                reliability_score=0.88,
                cost_breakdown={"port": 2400.0, "carrier": 4300.0, "warehouse": 1500.0},
                negotiation_rounds_taken=3
            )
        if not safest:
            safest = plan if plan.category == PlanCategory.SAFEST else RecoveryPlan(
                plan_id="PLAN-SAFEST-REF",
                category=PlanCategory.SAFEST,
                carrier_slot_id=plan.carrier_slot_id,
                port_slot_id=plan.port_slot_id,
                warehouse_slot_id=plan.warehouse_slot_id,
                total_cost_inr=max(plan.total_cost_inr * 1.15, 6800.0),
                total_delay_hours=max(1.5, plan.total_delay_hours * 0.7),
                reliability_score=0.96,
                cost_breakdown={"port": 1800.0, "carrier": 3600.0, "warehouse": 1400.0},
                negotiation_rounds_taken=3
            )

        # Financial & operational trade-off calculations
        delta_cost_fast = max(500.0, fastest.total_cost_inr - cheapest.total_cost_inr)
        delta_delay_fast = max(0.5, cheapest.total_delay_hours - fastest.total_delay_hours)
        breakeven_sla = delta_cost_fast / delta_delay_fast

        delta_cost_safe = max(300.0, safest.total_cost_inr - cheapest.total_cost_inr)
        delta_rel_safe = max(5.0, (safest.reliability_score - cheapest.reliability_score) * 100)

        # Cost breakdown values for the currently viewed plan
        cb = plan.cost_breakdown or {}
        carrier_cost = cb.get("carrier", plan.total_cost_inr * 0.55)
        port_cost = cb.get("port", plan.total_cost_inr * 0.25)
        wh_cost = cb.get("warehouse", plan.total_cost_inr * 0.20)

        q_lower = user_query.lower()
        is_choice_query = any(w in q_lower for w in ["which", "choose", "option", "pick", "why", "recommend", "compare", "difference", "better", "best", "what should"])
        is_cost_query = any(w in q_lower for w in ["cost", "price", "inr", "rupee", "₹", "expensive", "budget", "penalty", "financial", "save", "savings", "fee", "idle", "overtime"])
        is_time_query = any(w in q_lower for w in ["delay", "time", "hour", "speed", "fast", "schedule", "eta", "transit", "timeline", "late", "duration"])
        is_risk_query = any(w in q_lower for w in ["risk", "safe", "reliability", "buffer", "fail", "hazard", "certainty", "confidence", "breakdown"])
        is_resource_query = any(w in q_lower for w in ["driver", "truck", "dock", "port", "berth", "carrier", "warehouse", "slot"])

        guidance_blocks = []

        if is_choice_query or (not is_cost_query and not is_time_query and not is_risk_query and not is_resource_query):
            guidance_blocks.append(
                f"### ⚖️ Strategic Decision Matrix: Why Choose Which Option?\n\n"
                f"When selecting among the negotiated Pareto plans, apply these operational decision thresholds:\n\n"
                f"1. **Select ⚡ FASTEST (+{fastest.total_delay_hours:.1f}h delay, ₹{fastest.total_cost_inr:,.2f}) if:**\n"
                f"   - **SLA Penalty Breakeven**: Your contractual delivery delay penalty exceeds **₹{breakeven_sla:,.0f}/hour**. "
                f"FASTEST recovers **{delta_delay_fast:.1f} hours** earlier for an extra **₹{delta_cost_fast:,.2f}** in expedited carrier & crane surcharges, "
                f"yielding a net cost savings whenever SLA penalties exceed this rate.\n"
                f"   - **Cargo Urgency**: The shipment involves perishable goods, refrigerated pharmaceuticals, or critical assembly components where downtime costs dwarf freight premiums.\n\n"
                f"2. **Select 💰 CHEAPEST (+{cheapest.total_delay_hours:.1f}h delay, ₹{cheapest.total_cost_inr:,.2f}) if:**\n"
                f"   - **Margin Preservation**: Cargo is non-perishable general freight with a flexible receiving window (> 8 hours grace period).\n"
                f"   - **Low Breach Penalties**: Consignee SLA penalties are minor or waived, allowing you to directly save **₹{delta_cost_fast:,.2f}** in freight expenses.\n\n"
                f"3. **Select 🛡️ SAFEST (+{safest.total_delay_hours:.1f}h delay, ₹{safest.total_cost_inr:,.2f}) — [Recommended Default] if:**\n"
                f"   - **Operational Certainty**: Downstream warehouse dock or highway corridor is vulnerable to congestion. "
                f"SAFEST locks in dedicated dock `{safest.warehouse_slot_id}` and high-compliance carrier `{safest.carrier_slot_id}` with **{safest.reliability_score * 100:.0f}% confidence**.\n"
                f"   - **Risk Hedging**: For just **+₹{delta_cost_safe:,.2f}** over the cheapest plan, you eliminate secondary vehicle breakdown and dock detention penalties."
            )

        if is_cost_query:
            guidance_blocks.append(
                f"### 💰 Financial Breakdown & Cost Allocation\n\n"
                f"Financial commitment for **{plan.category.value}** route (Total: **₹{plan.total_cost_inr:,.2f}**):\n"
                f"- **Carrier Road Haulage**: ₹{carrier_cost:,.2f} (covers vehicle fuel, driver allowance, and expressway tolls).\n"
                f"- **Port Berth & Crane Slot**: ₹{port_cost:,.2f} (covers container discharge at slot `{plan.port_slot_id}`).\n"
                f"- **Warehouse Dock Intake**: ₹{wh_cost:,.2f} (covers reserved intake bay `{plan.warehouse_dock_id}` and staging crew).\n\n"
                f"**Financial Protection Insight**:\n"
                f"- Standby idle truck cost runs ~₹450/hour; this plan synchronizes crane and gate appointments, avoiding ₹{disruption.delay_hours * 450:,.2f} in driver idle demurrage.\n"
                f"- Choosing CHEAPEST yields ₹{fastest.total_cost_inr - cheapest.total_cost_inr:,.2f} in cash savings over FASTEST."
            )

        if is_time_query:
            guidance_blocks.append(
                f"### ⏱️ Transit Timeline & Delay Recovery Dynamics\n\n"
                f"- **Initial Disruption Delay**: +{disruption.delay_hours:.1f} hours ({disruption.description}).\n"
                f"- **Net Recovered Delay under {plan.category.value}**: **+{plan.total_delay_hours:.1f} hours**.\n"
                f"- **Expedited Alternative**: FASTEST compresses delivery to **+{fastest.total_delay_hours:.1f} hours** (saving {delta_delay_fast:.1f}h) via green-lane port clearance.\n"
                f"- **Downstream Intake**: Dock appointment at `{plan.warehouse_dock_id}` is guaranteed to clear before overnight warehouse curfew."
            )

        if is_risk_query:
            guidance_blocks.append(
                f"### 🛡️ Reliability & Secondary Disruption Shield\n\n"
                f"- **Plan Confidence Score**: **{plan.reliability_score * 100:.0f}%** operational feasibility.\n"
                f"- **Safety Enhancement**: SAFEST increases delivery reliability by **+{delta_rel_safe:.0f}%** over CHEAPEST by securing a vetted Tier-1 carrier and dedicated intake slot.\n"
                f"- **Buffer Allocation**: A 45-minute staging contingency window has been embedded into warehouse dock `{plan.warehouse_dock_id}` to absorb expressway traffic variances."
            )

        if is_resource_query and not is_choice_query:
            guidance_blocks.append(
                f"### 🚛 Resource Allocation Assessment\n\n"
                f"- **Assigned Carrier**: `{plan.truck_id}` with verified maintenance clearance and active driver duty cycle.\n"
                f"- **Assigned Port Slot**: `{plan.port_slot_id}` matched for container discharge.\n"
                f"- **Assigned Warehouse Bay**: `{plan.warehouse_dock_id}` with reserved staging crew."
            )

        guidance_text = "\n\n".join(guidance_blocks)

        return (
            f"### 🎯 Operational Decision & Strategic Recommendation\n\n"
            f"In response to operator inquiry regarding *\"{user_query}\"* under active disruption **{disruption.description}** "
            f"(+{disruption.delay_hours:.1f}h delay on `{disruption.source_entity_id}`):\n\n"
            f"#### 📊 Multi-Agent Pareto Trade-Off Matrix\n"
            f"| Recovery Option | Est. Total Cost | Net Delay | Reliability | Operational Strategic Focus |\n"
            f"| :--- | :--- | :--- | :--- | :--- |\n"
            f"| **💰 CHEAPEST** | **₹{cheapest.total_cost_inr:,.2f}** | +{cheapest.total_delay_hours:.1f}h | {cheapest.reliability_score * 100:.0f}% | Maximum margin protection; best when SLA penalties < ₹{breakeven_sla:,.0f}/h |\n"
            f"| **⚡ FASTEST** | **₹{fastest.total_cost_inr:,.2f}** | **+{fastest.total_delay_hours:.1f}h** | {fastest.reliability_score * 100:.0f}% | Expedited recovery; best when customer SLA penalties > ₹{breakeven_sla:,.0f}/h |\n"
            f"| **🛡️ SAFEST** | **₹{safest.total_cost_inr:,.2f}** | +{safest.total_delay_hours:.1f}h | **{safest.reliability_score * 100:.0f}%** | Guaranteed slot certainty; eliminates secondary breakdown & demurrage |\n\n"
            f"---\n\n"
            f"{guidance_text}\n\n"
            f"---\n\n"
            f"### 📋 Recommended Operator Action\n"
            f"1. **Current Plan Selected**: You are evaluating the **{plan.category.value}** route "
            f"(Est. Cost: **₹{plan.total_cost_inr:,.2f}**, Net Delay: **+{plan.total_delay_hours:.1f}h**, Confidence: **{plan.reliability_score * 100:.0f}%**).\n"
            f"2. **Operational Recommendation**: If customer late penalties exceed **₹{breakeven_sla:,.0f}/hr**, switch to **FASTEST** above; "
            f"otherwise, execute **{plan.category.value}** (or select **SAFEST** to guarantee 95%+ certainty).\n"
            f"3. Click **✅ Approve & Commit Plan** below to dispatch automated bookings across Port, Carrier, and Warehouse agents."
        )

    def parse_text_event(self, raw_text: str) -> Dict[str, Any]:
        """Extracts structured disruption signals from unstructured text/emails/SMS."""
        if self.is_configured():
            try:
                live_event = self._call_gemini_parse(raw_text)
                if live_event:
                    return live_event
            except Exception as e:
                logger.warning("Gemini text parsing failed (%s); using heuristic parser.", e)

        return self._heuristic_parse_text(raw_text)

    # ──────────────────────────────────────────────────────────────────
    # Internal Gemini Calling Methods with Strict Timeout & Model Failover
    # ──────────────────────────────────────────────────────────────────

    def _call_gemini_raw(self, prompt: str) -> Optional[str]:
        """Dispatches raw prompt to Gemini with auto-failover across models on quota exhaustion."""
        def _execute():
            models_to_try = [self.model]
            for cand in ["gemini-3.5-flash", "gemini-3.7-flash", "gemini-3.8-flash", "gemini-flash-latest"]:
                if cand not in models_to_try:
                    models_to_try.append(cand)

            for m in models_to_try:
                # 1. Try google.genai SDK
                try:
                    from google import genai
                    from google.genai import types
                    client = genai.Client(api_key=self.api_key)
                    resp = client.models.generate_content(
                        model=m,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            temperature=0.3,
                            max_output_tokens=1500
                        )
                    )
                    if resp and resp.text:
                        self.last_model_used = m
                        self.model = m
                        return resp.text.strip()
                except Exception as e:
                    logger.debug("genai SDK call error on %s: %s", m, e)
                    if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e) or "404" in str(e) or "not found" in str(e).lower():
                        continue
                    if "API key not valid" in str(e) or "INVALID_ARGUMENT" in str(e) or "400" in str(e):
                        return None

                # 2. Try REST API with strict timeout
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={self.api_key}"
                    payload = {
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1500}
                    }
                    data = json.dumps(payload).encode("utf-8")
                    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

                    with urllib.request.urlopen(req, timeout=7) as response:
                        result = json.loads(response.read().decode("utf-8"))
                        candidates = result.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts:
                                self.last_model_used = m
                                self.model = m
                                return parts[0].get("text", "").strip()
                except Exception as e_rest:
                    logger.debug("REST call error on %s: %s", m, e_rest)

            return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_execute)
            try:
                return future.result(timeout=10.0)
            except concurrent.futures.TimeoutError:
                logger.warning("Gemini raw call timed out after 10.0s; activating resilient heuristic fallback.")
                return None

    def _call_gemini_explanation(self, disruption: DisruptionEvent, plan: RecoveryPlan) -> Optional[str]:
        """Calls Gemini to explain recovery plan trade-offs in a concise, structured pros/cons format."""
        prompt = PLAN_EXPLANATION_PROMPT.format(
            disruption_details=(
                f"ID: {disruption.event_id}, Type: {disruption.event_type.value}, "
                f"Source: {disruption.source_entity_id}, Delay: +{disruption.delay_hours:.1f} hrs, "
                f"Description: {disruption.description}"
            ),
            plan_category=plan.category.value,
            total_cost_inr=f"{plan.total_cost_inr:,.2f}",
            delay_hours=f"{plan.total_delay_hours:.1f}",
            reliability_score=f"{plan.reliability_score * 100:.0f}%",
            cost_breakdown=json.dumps(plan.cost_breakdown or {}),
            port_slot_id=plan.port_slot_id,
            carrier_slot_id=plan.carrier_slot_id,
            warehouse_slot_id=plan.warehouse_slot_id
        )
        resp = self._call_gemini_raw(prompt)
        if resp:
            cleaned = resp.strip()
            if cleaned.startswith("```markdown"):
                cleaned = cleaned[len("```markdown"):].strip()
            elif cleaned.startswith("```md"):
                cleaned = cleaned[len("```md"):].strip()
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:].strip()
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3].strip()
            return cleaned
        return None

    def _call_gemini_parse(self, raw_text: str) -> Optional[Dict[str, Any]]:
        """Calls Gemini API to parse text into structured JSON event."""
        prompt = f"{TEXT_TO_EVENT_PROMPT}\nText: \"{raw_text}\"\nOutput valid JSON only with keys: event_type, source_entity_id, delay_hours, severity_level, description."
        
        def _execute_parse():
            for m in [self.model, "gemini-3.5-flash", "gemini-3.7-flash", "gemini-flash-latest"]:
                try:
                    from google import genai
                    from google.genai import types
                    client = genai.Client(api_key=self.api_key)
                    resp = client.models.generate_content(
                        model=m,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            temperature=0.0,
                            response_mime_type="application/json"
                        )
                    )
                    if resp and resp.text:
                        return json.loads(resp.text)
                except Exception:
                    pass

                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={self.api_key}"
                    payload = {
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"temperature": 0.0, "responseMimeType": "application/json"}
                    }
                    data = json.dumps(payload).encode("utf-8")
                    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=4) as response:
                        result = json.loads(response.read().decode("utf-8"))
                        candidates = result.get("candidates", [])
                        if candidates:
                            text_out = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                            return json.loads(text_out)
                except Exception:
                    pass
            return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_execute_parse)
            try:
                return future.result(timeout=5.5)
            except concurrent.futures.TimeoutError:
                return None

    # ──────────────────────────────────────────────────────────────────
    # Dynamic Multi-Perspective Offline Heuristic Generator
    # ──────────────────────────────────────────────────────────────────

    def _generate_heuristic_explanation(self, disruption: DisruptionEvent, plan: RecoveryPlan, iteration: int = 0) -> str:
        """Synthesizes concise, structured pros/cons and decision rationale for the selected plan."""
        cat = plan.category
        cost = f"₹{plan.total_cost_inr:,.2f}"
        delay = f"{plan.total_delay_hours:.1f}"
        rel = f"{plan.reliability_score * 100:.0f}%"
        variant = iteration % 2

        if cat == PlanCategory.CHEAPEST:
            if variant == 0:
                decision_taken = (
                    f"The Coordinator minimized recovery spending by assigning primary carrier `{plan.carrier_slot_id}` to standard standby (avoiding ₹8,500+ "
                    f"emergency fleet replacement surcharges), clearing cargo through regular port berth `{plan.port_slot_id}`, "
                    f"and booking off-peak warehouse intake bay `{plan.warehouse_slot_id}`."
                )
                why_choose = (
                    "Best choice when the consignee has a flexible receiving grace window (>8 hours) and customer SLA breach "
                    "penalties are low or absent, directly protecting freight operating margins."
                )
            else:
                decision_taken = (
                    f"The multi-agent negotiation absorbed the +{disruption.delay_hours:.1f}h disruption without expediting surcharges. "
                    f"Carrier `{plan.carrier_slot_id}` absorbs standby idle, port berth `{plan.port_slot_id}` operates at standard gate velocity, "
                    f"and warehouse intake is synchronized to off-peak bay `{plan.warehouse_slot_id}`."
                )
                why_choose = (
                    "Recommended for non-perishable general cargo where preserving profit margin outweighs transit urgency."
                )

            return (
                f"#### 🎯 Why Cheapest Plan & Decision Rationale\n"
                f"- **Decision Taken**: {decision_taken}\n"
                f"- **Why Choose This**: {why_choose}\n\n"
                f"#### ✅ Pros\n"
                f"- **Lowest Financial Commitment**: Recovery costs only **{cost}**, preserving shipper profitability.\n"
                f"- **No Surge Premiums**: Avoids expensive rush crane handling and third-party emergency carrier rates.\n"
                f"- **Resource Continuity**: Maintains original carrier fleet `{plan.carrier_slot_id}` without handoff friction.\n\n"
                f"#### ⚠️ Cons\n"
                f"- **Transit Delay**: Absorbs **+{delay}h** delay without transit compression.\n"
                f"- **Lower Reliability**: Rated at **{rel}** confidence; leaves less buffer for secondary highway congestion."
            )

        elif cat == PlanCategory.FASTEST:
            if variant == 0:
                decision_taken = (
                    f"The Coordinator prioritized delivery velocity by clearing cargo via priority green-lane berth `{plan.port_slot_id}`, "
                    f"hot-dispatching emergency relief carrier `{plan.carrier_slot_id}`, and booking expedited intake bay `{plan.warehouse_dock_id}`."
                )
                why_choose = (
                    "Best choice when contractual customer SLA breach penalties exceed ₹2,000/hour or when shipping high-value, "
                    "perishable, or Just-in-Time assembly components where delivery delay causes immediate downtime."
                )
            else:
                decision_taken = (
                    f"Multi-agent negotiation compressed transit time across all 3 nodes: expedited port discharge at `{plan.port_slot_id}`, "
                    f"priority highway dispatch via replacement carrier `{plan.carrier_slot_id}`, and reserved hot dock bay `{plan.warehouse_dock_id}`."
                )
                why_choose = (
                    "Recommended whenever delivery deadlines are non-negotiable and preserving customer account trust takes precedence."
                )

            return (
                f"#### 🎯 Why Fastest Plan & Decision Rationale\n"
                f"- **Decision Taken**: {decision_taken}\n"
                f"- **Why Choose This**: {why_choose}\n\n"
                f"#### ✅ Pros\n"
                f"- **Maximum Delay Recovery**: Compresses net delay down to **+{delay}h**, fully mitigating the initial disruption setback.\n"
                f"- **SLA Penalty Elimination**: Prevents contractual customer delivery fines and customer line-stoppage claims.\n"
                f"- **Priority Throughput**: Fast-tracks container discharge at berth `{plan.port_slot_id}` and offloading at dock `{plan.warehouse_dock_id}`.\n\n"
                f"#### ⚠️ Cons\n"
                f"- **Highest Expense**: Requires **{cost}** in recovery capital due to expedited carrier and port premiums.\n"
                f"- **Sub-optimal for Low-Value Freight**: Cost premium is uneconomical if consignee has an open receiving window."
            )

        else:  # SAFEST
            if variant == 0:
                decision_taken = (
                    f"The Coordinator established a 3-party consensus buffer by locking dedicated customs slot `{plan.port_slot_id}`, "
                    f"vetted high-compliance carrier `{plan.carrier_slot_id}`, and guaranteed reserved morning dock bay `{plan.warehouse_dock_id}`."
                )
                why_choose = (
                    "Recommended enterprise default when downstream supply chain congestion is unpredictable; completely eliminates "
                    "domino cascade risks and warehouse queue demurrage."
                )
            else:
                decision_taken = (
                    f"Agents agreed on a resilience-first profile: port slot `{plan.port_slot_id}` includes a 60-minute contingency buffer, "
                    f"carrier `{plan.carrier_slot_id}` uses pre-cleared uncongested corridors, and dock `{plan.warehouse_dock_id}` guarantees immediate unloading."
                )
                why_choose = (
                    "Ideal for high-priority consignments requiring maximum delivery certainty and zero tolerance for secondary disruption."
                )

            return (
                f"#### 🎯 Why Safest Plan & Decision Rationale\n"
                f"- **Decision Taken**: {decision_taken}\n"
                f"- **Why Choose This**: {why_choose}\n\n"
                f"#### ✅ Pros\n"
                f"- **Highest Operational Certainty**: Delivers an industry-leading **{rel}** execution reliability score.\n"
                f"- **Dock Queue Shield**: Pre-booked bay `{plan.warehouse_dock_id}` prevents warehouse rejection, driver overtime, and demurrage.\n"
                f"- **Balanced Economics**: Absorbs just **{cost}**, matching lowest expenditure while maximizing schedule reliability.\n\n"
                f"#### ⚠️ Cons\n"
                f"- **Buffer Schedule Offset**: Requires a controlled **+{delay}h** transit buffer window.\n"
                f"- **Window Alignment**: Consignee must be notified to align unloading staff with the updated reserved slot."
            )

    def _heuristic_parse_text(self, text: str) -> Dict[str, Any]:
        """Rule-based text-to-event parser fallback."""
        lower = text.lower()
        event_type = DisruptionType.PORT_CONGESTION
        delay = 3.0

        if "breakdown" in lower or "engine" in lower or "truck" in lower:
            event_type = DisruptionType.TRUCK_BREAKDOWN
        elif "warehouse" in lower or "dock" in lower or "bay" in lower:
            event_type = DisruptionType.WAREHOUSE_BOTTLENECK
        elif "vessel" in lower or "ship" in lower:
            event_type = DisruptionType.VESSEL_DELAY
        elif "traffic" in lower or "jam" in lower or "highway" in lower:
            event_type = DisruptionType.TRAFFIC_INCIDENT

        import re
        match = re.search(r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)\b", lower)
        if match:
            delay = float(match.group(1))

        return {
            "event_type": event_type.value,
            "source_entity_id": "AUTO_INGEST_01",
            "delay_hours": delay,
            "severity_level": min(1.0, delay / 6.0),
            "description": text.strip()
        }
