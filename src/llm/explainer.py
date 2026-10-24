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


def human_carrier_label(slot_id: Optional[str], category: Optional[PlanCategory] = None) -> str:
    """Translates internal carrier slot code into human-readable logistics wording."""
    s = (slot_id or "").upper()
    if "REPLACEMENT" in s:
        return "Emergency relief backup truck"
    if category == PlanCategory.SAFEST or "PROTECTED" in s:
        return "Protected primary carrier (with GPS dynamic rerouting)"
    return "Primary carrier on standby (same driver, zero cargo transfer)"


def human_warehouse_label(slot_id: Optional[str]) -> str:
    """Translates internal dock bay code into human-readable logistics wording."""
    s = (slot_id or "").upper()
    if "OVERTIME" in s:
        return "Priority evening overtime bay (dedicated turnaround crew)"
    if "R3" in s or "RESERVED" in s:
        return "Guaranteed reserved morning bay (08:00 AM slot)"
    if "MORNING" in s:
        return "Next-morning intake bay (08:00 AM regular shift)"
    return "Standard warehouse intake bay"


def human_port_label(slot_id: Optional[str]) -> str:
    """Translates internal port slot code into human-readable logistics wording."""
    s = (slot_id or "").upper()
    if "EXPRESS" in s or "R2" in s:
        return "Priority green-lane express berth (fast-track crane)"
    if "DELAYED" in s or "R1" in s:
        return "Standard clearance berth"
    return "Scheduled container berth"


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
                f"This plan commits recovery operating fee ₹{plan.total_cost_inr:,.2f} with +{plan.total_delay_hours:.1f}h transit delay "
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
        plans = {p.category: p for p in (all_plans or [])}
        plans[plan.category] = plan
        rows = []
        for category in (PlanCategory.CHEAPEST, PlanCategory.FASTEST, PlanCategory.SAFEST):
            option = plans.get(category)
            if option is None:
                rows.append(f"| {category.value} | Not supplied | — | — |")
            else:
                rows.append(f"| {category.value} | ₹{option.total_cost_inr:,.2f} | +{option.total_delay_hours:.1f}h | {option.reliability_score * 100:.0f}% |")
        breakdown = "\n".join(f"- **{key.title()}**: ₹{value:,.2f}" for key, value in (plan.cost_breakdown or {}).items())
        cheap, fast = plans.get(PlanCategory.CHEAPEST), plans.get(PlanCategory.FASTEST)
        breakeven = "Not calculated: both plans and a positive delay difference are required."
        if cheap and fast and cheap.total_delay_hours > fast.total_delay_hours:
            premium = fast.total_cost_inr - cheap.total_cost_inr
            hours = cheap.total_delay_hours - fast.total_delay_hours
            breakeven = f"Indicative operating-fee premium ₹{premium:,.2f} / {hours:.1f}h = ₹{premium / hours:,.2f}/h. Actual SLA penalties depend on the contractual deadline."
        return (
            "### 🎯 Operational Decision & Strategic Recommendation\n\n"
            f"Active shipment: **{disruption.source_entity_id}**, {disruption.description}.\n\n"
            "#### Multi-Agent Pareto Trade-Off Matrix\n"
            "| Recovery Option | Operating Fee | Coordinator Delay | Reliability |\n"
            "| :--- | ---: | ---: | ---: |\n" + "\n".join(rows) + "\n\n"
            "### Why Choose Which Option?\n"
            "CHEAPEST minimizes the negotiated operating fee; FASTEST minimizes the coordinator delay estimate; SAFEST maximizes the modeled reliability. Missing alternatives are not fabricated.\n\n"
            f"**SLA Penalty Breakeven:** {breakeven}\n\n"
            f"### Financial Breakdown — {plan.category.value}\n"
            f"Recovery operating fee: **₹{plan.total_cost_inr:,.2f}**.\n{breakdown}\n\n"
            "Fees exclude residual SLA penalties. Comparing an operating fee with unmitigated exposure does not establish net savings.\n\n"
            f"Selected resources: {plan.port_slot_id}, {plan.carrier_slot_id}, {plan.warehouse_slot_id}."
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
                            temperature=0.7,
                            max_output_tokens=2048
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
                        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 2048}
                    }
                    data = json.dumps(payload).encode("utf-8")
                    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

                    with urllib.request.urlopen(req, timeout=15) as response:
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
                return future.result(timeout=20.0)
            except concurrent.futures.TimeoutError:
                logger.warning("Gemini raw call timed out after 20.0s; activating resilient heuristic fallback.")
                return None

    def _call_gemini_explanation(self, disruption: DisruptionEvent, plan: RecoveryPlan) -> Optional[str]:
        """Calls Gemini to deliver a natural, expressive, and unconstrained operational briefing for the recovery plan."""
        carrier_human = human_carrier_label(plan.carrier_slot_id, plan.category)
        dock_human = human_warehouse_label(plan.warehouse_dock_id or plan.warehouse_slot_id)
        port_human = human_port_label(plan.port_slot_id)

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
            port_slot_id=f"Port: {port_human}",
            carrier_slot_id=f"Carrier: {carrier_human}",
            warehouse_slot_id=f"Warehouse Intake Bay: {dock_human}"
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
        """Synthesizes concise, structured pros/cons and decision rationale dynamically tailored to disruption type in human-friendly terms."""
        cat = plan.category
        cost = f"₹{plan.total_cost_inr:,.2f}"
        delay = f"{plan.total_delay_hours:.1f}"
        rel = f"{plan.reliability_score * 100:.0f}%"
        variant = iteration % 2

        # Disruption category classification
        dtype = disruption.event_type if isinstance(disruption.event_type, DisruptionType) else DisruptionType(str(disruption.event_type))
        is_road = dtype in (DisruptionType.TRAFFIC_INCIDENT, DisruptionType.TRUCK_BREAKDOWN)
        is_whs = dtype == DisruptionType.WAREHOUSE_BOTTLENECK
        road_name = "Expressway Traffic Congestion" if dtype == DisruptionType.TRAFFIC_INCIDENT else "Carrier Truck Breakdown"

        # ─────────────────────────────────────────────────────────────
        # 1. Road Transit Disruptions (Traffic Incident / Truck Breakdown)
        # ─────────────────────────────────────────────────────────────
        if is_road:
            if cat == PlanCategory.CHEAPEST:
                if variant == 0:
                    decision_taken = (
                        f"The primary driver remains on standby to wait out the highway delay (+{disruption.delay_hours:.1f}h) "
                        f"without hiring an expensive backup truck, while the destination warehouse reschedules intake to tomorrow's "
                        f"regular morning shift to avoid night overtime wages at the applied tariff."
                    )
                    why_choose = (
                        "Best choice for non-perishable general freight when the customer has a flexible receiving schedule "
                        "and saving operational costs is the top priority."
                    )
                else:
                    decision_taken = (
                        f"The coordinator absorbed the highway delay (+{disruption.delay_hours:.1f}h) by keeping the original truck on standby "
                        f"until traffic cleared—avoiding emergency fleet replacement surcharges—and moving warehouse intake to an off-peak morning bay."
                    )
                    why_choose = (
                        "Recommended for non-urgent shipments where contractual late delivery penalties are minor or waived, "
                        "maximizing operational profit margins."
                    )

                timing_con = (
                    "- **Next-Day Morning Delivery**: Arrival is deferred to tomorrow morning (8:00 AM) to avoid costly night-shift overtime fees."
                    if plan.total_delay_hours >= 12.0
                    else f"- **Transit Delay**: Absorbs **+{delay}h** transit delay without highway compression."
                )

                return (
                    f"#### 🎯 Why Cheapest Plan & Decision Rationale ({road_name})\n"
                    f"- **Decision Taken**: {decision_taken}\n"
                    f"- **Why Choose This**: {why_choose}\n\n"
                    f"#### ✅ Pros\n"
                    f"- **Lowest Financial Commitment**: Absorbs just **{cost}**, completely avoiding emergency third-party carrier surcharges.\n"
                    f"- **Zero Cargo Transfer Risk**: Retains the original driver and truck, eliminating the risk of cargo damage from emergency transfers.\n"
                    f"- **No Missed-Slot Penalties**: Warehouse intake is synchronized with the new arrival time, waiving missed-appointment fines.\n\n"
                    f"#### ⚠️ Cons\n"
                    f"{timing_con}\n"
                    f"- **Lower Reliability Buffer**: Rated at **{rel}** confidence; leaves less buffer if downstream road bottlenecks occur."
                )

            elif cat == PlanCategory.FASTEST:
                if variant == 0:
                    decision_taken = (
                        f"To bypass the {road_name.lower()} (+{disruption.delay_hours:.1f}h), the carrier dispatched an emergency backup relief truck "
                        f"via open expressway bypass lanes, while the destination warehouse activated a priority overtime evening dock door to unload cargo tonight."
                    )
                    why_choose = (
                        "Essential when customer contractual late-delivery penalties exceed the additional recovery operating fee or when shipping high-value "
                        "Just-in-Time components where delayed delivery halts a factory production line."
                    )
                else:
                    decision_taken = (
                        f"The coordinator compressed transit time across the highway leg by swapping in an emergency relief carrier "
                        f"on clear alternate lanes, backed by an expedited evening warehouse bay for immediate same-day offloading."
                    )
                    why_choose = (
                        "Recommended when customer delivery deadlines are strictly non-negotiable and preserving SLA compliance takes precedence."
                    )

                return (
                    f"#### 🎯 Why Fastest Plan & Decision Rationale ({road_name})\n"
                    f"- **Decision Taken**: {decision_taken}\n"
                    f"- **Why Choose This**: {why_choose}\n\n"
                    f"#### ✅ Pros\n"
                    f"- **Same-Day Delivery (0h Added Delay)**: Compresses net delay down to **+{delay}h**, completely mitigating the highway setback.\n"
                    f"- **Zero SLA Penalties**: Prevents contractual customer delivery fines and customer line-stoppage claims.\n"
                    f"- **Priority Gate Turnaround**: Dedicated overtime dock crew unloads the shipment immediately upon arrival with zero queue wait.\n\n"
                    f"#### ⚠️ Cons\n"
                    f"- **Emergency Premium**: Requires **{cost}** in recovery spend due to expedited backup trucking rates and overtime warehouse labor.\n"
                    f"- **Uneconomical for Routine Freight**: Surcharge is unnecessary if the consignee has flexible receiving hours."
                )

            else:  # SAFEST
                if variant == 0:
                    decision_taken = (
                        f"The coordinator guided the existing driver along pre-cleared arterial detour routes with real-time GPS tracking "
                        f"to avoid traffic jams, while the destination warehouse locked a guaranteed reserved morning bay (08:00 AM) for instant offloading."
                    )
                    why_choose = (
                        "Recommended enterprise default when highway conditions are unpredictable and you cannot risk vehicle breakdown, "
                        "driver detention penalties, or warehouse gate rejection."
                    )
                else:
                    decision_taken = (
                        f"A resilient 3-party consensus was established: the carrier navigates pre-cleared secondary detour corridors with GPS tracking, "
                        f"and the destination warehouse guarantees 100% bay clearance certainty tomorrow morning at 08:00 AM."
                    )
                    why_choose = (
                        "Ideal for high-priority consignments requiring maximum delivery certainty and zero tolerance for secondary disruption."
                    )

                timing_con = (
                    "- **Next-Day Morning Delivery**: Arrival shifts to tomorrow morning (8:00 AM) to maintain a controlled, protected receiving window."
                    if plan.total_delay_hours >= 12.0
                    else f"- **Controlled Buffer Window**: Operates with a controlled **+{delay}h** schedule buffer."
                )

                return (
                    f"#### 🎯 Why Safest Plan & Decision Rationale ({road_name})\n"
                    f"- **Decision Taken**: {decision_taken}\n"
                    f"- **Why Choose This**: {why_choose}\n\n"
                    f"#### ✅ Pros\n"
                    f"- **Highest Operational Certainty**: Delivers an industry-leading **{rel}** execution reliability score with built-in route buffer.\n"
                    f"- **Guaranteed Gate Clearance**: Pre-booked morning bay guarantees zero waiting at the warehouse gate and prevents driver overtime penalties.\n"
                    f"- **Balanced Cost**: Absorbs just **{cost}**, the negotiated operating fee, excluding residual penalties.\n\n"
                    f"#### ⚠️ Cons\n"
                    f"{timing_con}\n"
                    f"- **Customer Notice Needed**: Consignee receiving staff must be notified to prepare for the 8:00 AM morning arrival slot."
                )

        # ─────────────────────────────────────────────────────────────
        # 2. Destination Warehouse Bottleneck
        # ─────────────────────────────────────────────────────────────
        elif is_whs:
            if cat == PlanCategory.CHEAPEST:
                if variant == 0:
                    decision_taken = (
                        f"Road transit arrived on schedule; to bypass destination dock queues (+{disruption.delay_hours:.1f}h), the truck is held overnight in the "
                        f"secure depot yard, rescheduling offloading to tomorrow's regular morning shift bay to save night overtime wages at the applied tariff "
                        f"and waive the missed-slot penalty at the applied tariff."
                    )
                    why_choose = (
                        "Best choice when freight can safely stage overnight in the secure depot yard and avoiding dock overtime surcharges is prioritized."
                    )
                else:
                    decision_taken = (
                        f"The coordinator avoided dock overtime premiums by holding the truck in secure staging overnight and "
                        f"synchronizing offloading with tomorrow's regular morning shift crew."
                    )
                    why_choose = (
                        "Recommended for non-urgent shipments where saving labor surcharges protects operational margins."
                    )

                return (
                    f"#### 🎯 Why Cheapest Plan & Decision Rationale (Warehouse Bottleneck)\n"
                    f"- **Decision Taken**: {decision_taken}\n"
                    f"- **Why Choose This**: {why_choose}\n\n"
                    f"#### ✅ Pros\n"
                    f"- **Lowest Financial Commitment**: Recovery costs only **{cost}**, completely saving evening dock overtime wages.\n"
                    f"- **Demurrage Penalty Waiver**: Automated multi-agent consensus waives missed-intake cancellation penalties.\n"
                    f"- **Driver Rest & Safety**: Driver rests in the secure staging yard without incurring gate idling fines or fatigue violations.\n\n"
                    f"#### ⚠️ Cons\n"
                    f"- **Next-Day Morning Offloading**: Warehouse intake is deferred to tomorrow morning (8:00 AM).\n"
                    f"- **Depot Staging**: Requires the shipment to remain staged in the trailer until the morning intake shift opens."
                )

            elif cat == PlanCategory.FASTEST:
                if variant == 0:
                    decision_taken = (
                        f"Road transit arrived on schedule; to resolve dock congestion without delay, the warehouse authorized "
                        f"a priority evening overtime bay with a dedicated turnaround crew to unload the container tonight."
                    )
                    why_choose = (
                        "Best choice when cargo is urgently required for immediate retail fulfillment, hospital supply, or morning factory assembly line feed."
                    )
                else:
                    decision_taken = (
                        f"The coordinator eliminated warehouse congestion by activating an expedited dock bay with a dedicated crew, "
                        f"turning the truck around in under 60 minutes tonight."
                    )
                    why_choose = (
                        "Recommended whenever same-day delivery SLAs must be preserved at all costs."
                    )

                return (
                    f"#### 🎯 Why Fastest Plan & Decision Rationale (Warehouse Bottleneck)\n"
                    f"- **Decision Taken**: {decision_taken}\n"
                    f"- **Why Choose This**: {why_choose}\n\n"
                    f"#### ✅ Pros\n"
                    f"- **Zero Delivery Lag**: Compresses intake delay down to **+{delay}h**, preserving the customer delivery SLA today.\n"
                    f"- **Dedicated Intake Door**: Immediate cargo intake at a priority bay with zero gate queue delay.\n"
                    f"- **Fast Fleet Turnaround**: Releases the truck and driver in under 60 minutes for subsequent dispatches.\n\n"
                    f"#### ⚠️ Cons\n"
                    f"- **Overtime Labor Surcharge**: Commits **{cost}** due to after-hours warehouse overtime staffing.\n"
                    f"- **Uneconomical for General Freight**: Premium is uneconomical if customer SLA allows overnight hold."
                )

            else:  # SAFEST
                if variant == 0:
                    decision_taken = (
                        f"Avoids evening dock congestion by locking a guaranteed reserved morning intake bay (08:00 AM) "
                        f"with dedicated unloading equipment, eliminating gate bottlenecks entirely."
                    )
                    why_choose = (
                        "Recommended enterprise default for high-value freight where warehouse gate queues, trailer detention, "
                        "and intake rejection risks must be 100% eliminated."
                    )
                else:
                    decision_taken = (
                        f"The coordinator established dock certainty by locking a guaranteed morning intake bay, providing the carrier "
                        f"guaranteed clearance with **{rel}** execution confidence."
                    )
                    why_choose = (
                        "Ideal for consignments requiring maximum delivery certainty and zero tolerance for secondary warehouse demurrage."
                    )

                return (
                    f"#### 🎯 Why Safest Plan & Decision Rationale (Warehouse Bottleneck)\n"
                    f"- **Decision Taken**: {decision_taken}\n"
                    f"- **Why Choose This**: {why_choose}\n\n"
                    f"#### ✅ Pros\n"
                    f"- **Maximum Intake Reliability**: Delivers an industry-leading **{rel}** intake clearance certainty.\n"
                    f"- **Zero Demurrage Risk**: Pre-booked morning bay eliminates driver gate waiting, trailer detention fees, and bay rejection.\n"
                    f"- **Balanced Financials**: Absorbs just **{cost}**, the negotiated operating fee, excluding residual penalties.\n\n"
                    f"#### ⚠️ Cons\n"
                    f"- **Next-Day Morning Arrival**: Unloading is scheduled for tomorrow morning (8:00 AM).\n"
                    f"- **Slot Compliance**: Carrier must arrive strictly within the designated 8:00 AM morning receiving window."
                )

        # ─────────────────────────────────────────────────────────────
        # 3. Port & Maritime Disruptions (Port Congestion / Vessel Delay)
        # ─────────────────────────────────────────────────────────────
        else:
            port_name = "Port Berth Congestion" if dtype == DisruptionType.PORT_CONGESTION else "Vessel Arrival Delay"
            if cat == PlanCategory.CHEAPEST:
                if variant == 0:
                    decision_taken = (
                        f"The coordinator absorbed the {port_name.lower()} (+{disruption.delay_hours:.1f}h) by clearing cargo through standard berth queues "
                        f"without paying rush crane fees, placing the primary carrier on standard standby (avoiding emergency fleet replacement surcharges), "
                        f"and booking tomorrow's regular morning warehouse bay."
                    )
                    why_choose = (
                        "Best choice when the consignee has a flexible receiving grace window (>8 hours) and customer SLA breach "
                        "penalties are low or absent, directly protecting freight operating margins."
                    )
                else:
                    decision_taken = (
                        f"The multi-agent negotiation absorbed the +{disruption.delay_hours:.1f}h disruption without expediting surcharges: "
                        f"the primary carrier absorbs standby idle, the port berth operates at standard gate velocity, "
                        f"and warehouse intake is synchronized to tomorrow's regular morning shift."
                    )
                    why_choose = (
                        "Recommended for non-perishable general cargo where preserving profit margin outweighs transit urgency."
                    )

                timing_con = (
                    "- **Next-Day Morning Delivery**: Shipment arrives tomorrow morning (8:00 AM) due to standard clearance queues."
                    if plan.total_delay_hours >= 12.0
                    else f"- **Transit Delay**: Absorbs **+{delay}h** delay without transit compression."
                )

                return (
                    f"#### 🎯 Why Cheapest Plan & Decision Rationale ({port_name})\n"
                    f"- **Decision Taken**: {decision_taken}\n"
                    f"- **Why Choose This**: {why_choose}\n\n"
                    f"#### ✅ Pros\n"
                    f"- **Lowest Financial Commitment**: Recovery costs only **{cost}**, preserving shipper profitability.\n"
                    f"- **No Surge Premiums**: Avoids expensive rush crane handling and third-party emergency carrier rates.\n"
                    f"- **Resource Continuity**: Retains original carrier fleet without vehicle handoff friction.\n\n"
                    f"#### ⚠️ Cons\n"
                    f"{timing_con}\n"
                    f"- **Lower Reliability**: Rated at **{rel}** confidence; leaves less buffer for secondary highway congestion."
                )

            elif cat == PlanCategory.FASTEST:
                if variant == 0:
                    decision_taken = (
                        f"The coordinator prioritized delivery velocity by clearing cargo via a priority green-lane berth, "
                        f"hot-dispatching an emergency relief backup truck, and booking an expedited warehouse evening dock door."
                    )
                    why_choose = (
                        "Best choice when contractual customer SLA breach penalties exceed the additional recovery operating fee or when shipping high-value, "
                        "perishable, or Just-in-Time assembly components where delivery delay causes immediate downtime."
                    )
                else:
                    decision_taken = (
                        f"Multi-agent negotiation compressed transit time across all 3 nodes: expedited port discharge at green-lane berth, "
                        f"priority highway dispatch via relief carrier, and reserved hot dock door at warehouse."
                    )
                    why_choose = (
                        "Recommended whenever delivery deadlines are non-negotiable and preserving customer account trust takes precedence."
                    )

                return (
                    f"#### 🎯 Why Fastest Plan & Decision Rationale ({port_name})\n"
                    f"- **Decision Taken**: {decision_taken}\n"
                    f"- **Why Choose This**: {why_choose}\n\n"
                    f"#### ✅ Pros\n"
                    f"- **Maximum Delay Recovery**: Compresses net delay down to **+{delay}h**, fully mitigating the initial disruption setback.\n"
                    f"- **SLA Penalty Elimination**: Prevents contractual customer delivery fines and customer line-stoppage claims.\n"
                    f"- **Priority Throughput**: Fast-tracks container discharge at berth and offloading at destination dock with zero gate wait.\n\n"
                    f"#### ⚠️ Cons\n"
                    f"- **Highest Expense**: Requires **{cost}** in recovery spend due to expedited carrier and port crane premiums.\n"
                    f"- **Sub-optimal for Low-Value Freight**: Cost premium is uneconomical if consignee has an open receiving window."
                )

            else:  # SAFEST
                if variant == 0:
                    decision_taken = (
                        f"The coordinator established a resilient 3-party buffer by locking a dedicated customs clearance window, "
                        f"assigning a vetted carrier with real-time GPS tracking, and securing a guaranteed reserved morning dock door."
                    )
                    why_choose = (
                        "Recommended enterprise default when downstream supply chain congestion is unpredictable; completely eliminates "
                        "domino cascade risks and warehouse queue demurrage."
                    )
                else:
                    decision_taken = (
                        f"Agents agreed on a resilience-first profile: port berth includes a 60-minute contingency buffer, "
                        f"the carrier uses pre-cleared uncongested corridors, and the destination warehouse guarantees immediate morning unloading."
                    )
                    why_choose = (
                        "Ideal for high-priority consignments requiring maximum delivery certainty and zero tolerance for secondary disruption."
                    )

                timing_con = (
                    "- **Next-Day Morning Delivery**: Delivery is scheduled for tomorrow morning (8:00 AM) to maintain a controlled, protected arrival window."
                    if plan.total_delay_hours >= 12.0
                    else f"- **Controlled Buffer Window**: Operates with a controlled **+{delay}h** schedule buffer."
                )

                return (
                    f"#### 🎯 Why Safest Plan & Decision Rationale ({port_name})\n"
                    f"- **Decision Taken**: {decision_taken}\n"
                    f"- **Why Choose This**: {why_choose}\n\n"
                    f"#### ✅ Pros\n"
                    f"- **Highest Operational Certainty**: Delivers an industry-leading **{rel}** execution reliability score.\n"
                    f"- **Zero Demurrage Risk**: Pre-booked morning bay eliminates warehouse rejection, driver overtime, and gate demurrage.\n"
                    f"- **Balanced Economics**: Absorbs just **{cost}**, the negotiated operating fee, excluding residual penalties.\n\n"
                    f"#### ⚠️ Cons\n"
                    f"{timing_con}\n"
                    f"- **Receiving Alignment**: Customer warehouse receiving team must be notified to prepare for the 8:00 AM morning arrival."
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
