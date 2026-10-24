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
from typing import Dict, Any, Optional, Tuple

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

    def ask_custom_question(self, disruption: DisruptionEvent, plan: RecoveryPlan, user_query: str) -> str:
        """Allows human operators to interrogate the recovery plan using conversational AI."""
        if not self.is_configured():
            return (
                "⚠️ **Live Gemini API key not configured.**\n\n"
                f"Based on local logistics rules for **{plan.category.value}**: "
                f"This plan commits total cost ₹{plan.total_cost_inr:,.2f} with +{plan.total_delay_hours:.1f}h transit delay "
                f"and {plan.reliability_score * 100:.0f}% reliability. "
                "To ask customized interactive questions, enter your Google Gemini API key in the sidebar."
            )

        prompt = (
            f"You are FreightFlow AI's operational logistics advisor.\n"
            f"Active Disruption: {disruption.description} (Type: {disruption.event_type.value}, Delay: +{disruption.delay_hours:.1f}h)\n"
            f"Active Recovery Plan: {plan.category.value}\n"
            f"- Total Cost: ₹{plan.total_cost_inr:,.2f}\n"
            f"- Transit Delay: +{plan.total_delay_hours:.1f} hours\n"
            f"- Reliability: {plan.reliability_score * 100:.0f}%\n"
            f"- Resource Allocation: Port Slot {plan.port_slot_id}, Carrier {plan.truck_id}, Dock {plan.warehouse_dock_id}\n\n"
            f"Human Operator Question: \"{user_query}\"\n\n"
            f"Provide a concise, practical, logistics-grounded answer (2-4 sentences)."
        )

        try:
            return self._call_gemini_raw(prompt) or (
                f"Based on **{plan.category.value}** rules: Operator inquiry regarding '{user_query}' — "
                f"this recovery route absorbs ₹{plan.total_cost_inr:,.2f} total cost with {plan.reliability_score * 100:.0f}% confidence."
            )
        except Exception as e:
            return f"⚠️ Query error: {str(e)}"

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
                            max_output_tokens=600
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

                # 2. Try REST API with strict 4s timeout
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={self.api_key}"
                    payload = {
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 600}
                    }
                    data = json.dumps(payload).encode("utf-8")
                    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

                    with urllib.request.urlopen(req, timeout=4) as response:
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
                return future.result(timeout=6.0)
            except concurrent.futures.TimeoutError:
                logger.warning("Gemini raw call timed out after 6.0s; activating resilient heuristic fallback.")
                return None

    def _call_gemini_explanation(self, disruption: DisruptionEvent, plan: RecoveryPlan) -> Optional[str]:
        """Calls Gemini to explain recovery plan trade-offs."""
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
            cost_breakdown=json.dumps(plan.cost_breakdown or {})
        )
        return self._call_gemini_raw(prompt)

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
        """Synthesizes rich, dynamic operational trade-off rationale varying with iteration."""
        cat = plan.category
        cost = f"₹{plan.total_cost_inr:,.2f}"
        delay = f"{plan.total_delay_hours:.1f}"
        rel = f"{plan.reliability_score * 100:.0f}%"
        disruption_desc = disruption.description or f"{disruption.event_type.value} (+{disruption.delay_hours:.1f}h)"
        variant = iteration % 3

        if cat == PlanCategory.CHEAPEST:
            if variant == 0:
                return (
                    f"🟢 **[Cheapest Plan: Commercial Focus]**: Prioritizes strict financial cost containment ({cost}) by absorbing "
                    f"the +{disruption.delay_hours:.1f}h {disruption.event_type.value.lower().replace('_', ' ')} delay ({disruption_desc}). "
                    f"By avoiding expedited port crane charges and high-cost emergency replacement fleets, the carrier truck ({plan.carrier_slot_id}) "
                    f"remains on standard standby rates. Dock appointment is rescheduled to '{plan.warehouse_slot_id}' during off-peak hours. "
                    f"Projected transit delay is +{delay}h with {rel} schedule reliability. Recommended when demurrage and customer SLA penalties are low."
                )
            elif variant == 1:
                return (
                    f"🟢 **[Cheapest Plan: Fleet & Resource Impact]**: Allocates primary carrier fleet '{plan.carrier_slot_id}' on driver idle standby, "
                    f"avoiding ₹8,500+ premium replacement dispatch surcharges. The port berth '{plan.port_slot_id}' clears cargo under standard flow, "
                    f"deferring warehouse intake to intake bay '{plan.warehouse_slot_id}'. Total financial recovery commitment is {cost} with "
                    f"+{delay}h delivery offset. Suitable for bulk or non-perishable freight where delivery flexibility exists."
                )
            else:
                return (
                    f"🟢 **[Cheapest Plan: Risk & Penalty Mitigation]**: Strategic cost-minimizing trade-off: Total recovery expense is {cost} "
                    f"against nominal cascading exposure. The plan accepts +{delay}h transit deferral to preserve carrier driver legal duty hours and "
                    f"utilize off-peak warehouse intake windows at '{plan.warehouse_slot_id}'. Reliability is rated at {rel}. "
                    f"Recommended action: Authorize immediately if customer SLA breach penalties do not exceed accrued operational savings."
                )

        elif cat == PlanCategory.FASTEST:
            if variant == 0:
                return (
                    f"⚡ **[Fastest Plan: Velocity Priority]**: Maximizes delivery velocity by aggressively cutting end-to-end delay down to +{delay}h "
                    f"(fully mitigating the +{disruption.delay_hours:.1f}h {disruption.event_type.value.lower().replace('_', ' ')} setback). "
                    f"Authorizes priority crane discharge at berth '{plan.port_slot_id}' and hot-dispatches emergency backup truck '{plan.carrier_slot_id}'. "
                    f"Dock slot is locked at '{plan.warehouse_dock_id}' for expedited offloading. Total cost is {cost} with {rel} reliability. "
                    f"Recommended to preserve critical customer delivery SLAs and eliminate contract breach fines."
                )
            elif variant == 1:
                return (
                    f"⚡ **[Fastest Plan: Cross-Party Expediting]**: High-speed recovery protocol across all 3 logistics nodes: Port berths prioritize "
                    f"container discharge at '{plan.port_slot_id}', carrier dispatches replacement fleet '{plan.carrier_slot_id}', and warehouse reserves "
                    f"hot dock bay '{plan.warehouse_dock_id}'. Net delay is minimized to just +{delay}h (saving {max(0.0, disruption.delay_hours - plan.total_delay_hours):.1f}h). "
                    f"Total recovery investment: {cost} at {rel} execution reliability. Recommended for assembly line and time-critical consignments."
                )
            else:
                return (
                    f"⚡ **[Fastest Plan: Delivery Assurance]**: Compresses downstream transit latency to +{delay}h through simultaneous resource reallocation. "
                    f"By swapping stalled carrier units with hot-standby carrier '{plan.carrier_slot_id}' and expediting intake at dock '{plan.warehouse_dock_id}', "
                    f"customer delivery occurs within SLA target. Total plan cost is {cost}. Recommended action: Approve to protect customer trust."
                )

        else:  # SAFEST
            if variant == 0:
                return (
                    f"🛡️ **[Safest Plan: Resilience & Buffer Protected]**: Delivers the optimal balanced compromise achieving the highest operational "
                    f"stability ({rel} reliability score). Realigns trucking along guaranteed transit corridors with truck '{plan.carrier_slot_id}' "
                    f"and secures a protected reservation at warehouse dock '{plan.warehouse_dock_id}'. Total recovery cost is {cost} with a controlled "
                    f"+{delay}h transit buffer window. Recommended default choice to permanently eliminate domino failure risks across all parties."
                )
            elif variant == 1:
                return (
                    f"🛡️ **[Safest Plan: Multi-Party Consensus]**: Highest consensus alignment across Port, Carrier, and Warehouse agents. Port slot '{plan.port_slot_id}' "
                    f"incorporates a 60-minute handling safety buffer; carrier truck '{plan.carrier_slot_id}' avoids high-congestion highways; warehouse dock "
                    f"'{plan.warehouse_dock_id}' guarantees immediate bay clearance. Total plan cost is {cost} with {rel} confidence. "
                    f"Recommended action: Authorize for high-value cargo requiring zero downstream variance."
                )
            else:
                return (
                    f"🛡️ **[Safest Plan: Operational Stability Guarantee]**: Prioritizes schedule certainty ({rel} reliability) by constructing guaranteed "
                    f"transfer buffers between port release and warehouse intake. Eliminates driver fatigue violations and warehouse dock queue bottlenecks. "
                    f"Total recovery investment is {cost} with +{delay}h scheduled offset. Recommended action: Standard enterprise recovery choice."
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
