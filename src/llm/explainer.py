"""LLM client integration to translate disruptions into events and explain recovery plans.

Supports Google Gemini API via official google.genai SDK, legacy google.generativeai,
REST endpoints, with seamless offline heuristic fallback.
"""

from __future__ import annotations
import os
import json
import logging
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, Tuple

from src.common.schemas import RecoveryPlan, DisruptionEvent, DisruptionType, PlanCategory
from src.llm.prompts import PLAN_EXPLANATION_PROMPT, TEXT_TO_EVENT_PROMPT
from src.common.config import GEMINI_API_KEY, LLM_PROVIDER, GEMINI_MODEL

logger = logging.getLogger(__name__)


class LLMExplainer:
    """Provides human-readable justifications and interactive Q&A for recovery plans.
    
    Tries Google Gemini API first (using modern google-genai or REST), and falls back
    to a high-fidelity offline heuristic engine if no key is configured or network is unavailable.
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
        self.model = model or os.getenv("GEMINI_MODEL") or GEMINI_MODEL or "gemini-3.8-flash"
        self.last_source: str = "uninitialized"  # "gemini" or "heuristic"
        self.last_model_used: Optional[str] = None

    def is_configured(self) -> bool:
        """Returns True if a non-placeholder Gemini API key is configured."""
        return bool(self.api_key and self.api_key not in ("your_gemini_api_key_here", "AIzaSy..."))

    def test_connection(self, api_key: Optional[str] = None, model: Optional[str] = None) -> Tuple[bool, str]:
        """Validates the Gemini API key by making a lightweight ping to the model."""
        key = (api_key or self.api_key or "").strip()
        if not key or key in ("your_gemini_api_key_here", "AIzaSy..."):
            return False, "No valid API key provided. Please enter a valid Google Gemini API key."

        target_model = model or self.model
        prompt = "Hello! Please reply with exactly the word: OK"

        models_to_test = [target_model]
        if "gemini-3.8-flash" not in models_to_test:
            models_to_test.append("gemini-3.8-flash")
        if "gemini-3.5-flash" not in models_to_test:
            models_to_test.append("gemini-3.5-flash")

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
                        msg += f" (Auto-migrated from deprecated '{target_model}')"
                    return True, msg
            except Exception as e_sdk:
                last_error = str(e_sdk)
                logger.debug("genai SDK test failed for %s: %s", m, e_sdk)
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
                with urllib.request.urlopen(req, timeout=8) as response:
                    res_json = json.loads(response.read().decode("utf-8"))
                    candidates = res_json.get("candidates", [])
                    if candidates:
                        self.model = m
                        msg = f"Successfully connected to Gemini API via REST ('{m}')!"
                        if m != target_model:
                            msg += f" (Auto-migrated from deprecated '{target_model}')"
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

    def explain_plan(self, disruption: DisruptionEvent, plan: RecoveryPlan) -> str:
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

        # Fallback to high-fidelity deterministic heuristic explanation
        self.last_source = "heuristic"
        self.last_model_used = "FreightFlow Rule Engine"
        return self._generate_heuristic_explanation(disruption, plan)

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
            return self._call_gemini_raw(prompt) or "Unable to generate answer at this time."
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
    # Internal Gemini Calling Methods
    # ──────────────────────────────────────────────────────────────────

    def _call_gemini_raw(self, prompt: str) -> Optional[str]:
        """Dispatches raw prompt to Gemini via google.genai SDK or REST with fast timeout."""
        # 1. Try google.genai SDK
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=self.api_key)
            resp = client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=600
                )
            )
            if resp and resp.text:
                self.last_model_used = self.model
                return resp.text.strip()
        except Exception as e:
            logger.debug("genai SDK call error on %s: %s", self.model, e)
            if ("404" in str(e) or "not found" in str(e).lower()) and self.model != "gemini-3.8-flash":
                try:
                    resp = client.models.generate_content(
                        model="gemini-3.8-flash",
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            temperature=0.3,
                            max_output_tokens=600
                        )
                    )
                    if resp and resp.text:
                        self.last_model_used = "gemini-3.8-flash"
                        return resp.text.strip()
                except Exception:
                    pass

        # 2. Try REST API with strict 6-second timeout
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.3, "maxOutputTokens": 600}
            }
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

            with urllib.request.urlopen(req, timeout=6) as response:
                result = json.loads(response.read().decode("utf-8"))
                candidates = result.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        self.last_model_used = self.model
                        return parts[0].get("text", "").strip()
        except Exception as e_rest:
            logger.debug("REST call error on %s: %s", self.model, e_rest)

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
        
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=self.api_key)
            resp = client.models.generate_content(
                model=self.model,
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

        # Fallback to raw REST with responseMimeType
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.0, "responseMimeType": "application/json"}
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
            candidates = result.get("candidates", [])
            if candidates:
                text_out = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                return json.loads(text_out)
        return None

    # ──────────────────────────────────────────────────────────────────
    # Offline Intelligent Heuristic Generator
    # ──────────────────────────────────────────────────────────────────

    def _generate_heuristic_explanation(self, disruption: DisruptionEvent, plan: RecoveryPlan) -> str:
        """Synthesizes human-readable operational trade-off rationale."""
        cat = plan.category
        cost = f"₹{plan.total_cost_inr:,.2f}"
        delay = f"{plan.total_delay_hours:.1f}"
        rel = f"{plan.reliability_score * 100:.0f}%"

        disruption_desc = disruption.description or f"{disruption.event_type.value} (+{disruption.delay_hours:.1f}h)"

        if cat == PlanCategory.CHEAPEST:
            return (
                f"🟢 **[Cheapest Plan Analysis]**: Prioritizes financial cost containment ({cost}) by absorbing the "
                f"{disruption.delay_hours:.1f}h {disruption.event_type.value.lower().replace('_', ' ')} disruption ({disruption_desc}). "
                f"The carrier driver waits at standard standby rates rather than incurring premium replacement vehicle dispatch fees, "
                f"and downstream dock intake is aligned with available off-peak windows. "
                f"Projected transit delay is +{delay}h with {rel} schedule reliability. "
                f"**Recommended action:** Authorize when cargo is non-perishable and customer contractual SLA breach penalties are low."
            )
        elif cat == PlanCategory.FASTEST:
            return (
                f"⚡ **[Fastest Plan Analysis]**: Maximizes delivery velocity, compressing end-to-end delay to just "
                f"+{delay}h (mitigating the nominal +{disruption.delay_hours:.1f}h impact from {disruption_desc}). "
                f"Authorizes expedited handling at port berth '{plan.port_slot_id}' and hot-dispatches emergency priority carrier '{plan.truck_id}'. "
                f"Total recovery cost is {cost} with {rel} operational reliability. "
                f"**Recommended action:** Authorize immediately for high-priority shipments to avoid severe downstream assembly line or customer SLA penalties."
            )
        else:  # SAFEST
            return (
                f"🛡️ **[Safest Plan Analysis]**: Delivers the optimal balanced compromise achieving the highest operational stability "
                f"({rel} reliability score). Realigns trucking along guaranteed transit corridors and locks in a protected warehouse intake slot at '{plan.warehouse_dock_id}'. "
                f"Total recovery investment is {cost} with +{delay}h transit offset. "
                f"**Recommended action:** Recommended default choice for high-value freight to permanently eliminate compounding bottleneck risks across all parties."
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
