"""LLM client integration to translate disruptions into events and explain recovery plans.

Supports Google Gemini API via REST/SDK with intelligent offline fallback.
"""

from __future__ import annotations
import os
import json
import urllib.request
import urllib.error
from typing import Dict, Any, Optional

from src.common.schemas import RecoveryPlan, DisruptionEvent, DisruptionType, PlanCategory
from src.llm.prompts import PLAN_EXPLANATION_PROMPT, TEXT_TO_EVENT_PROMPT
from src.common.config import GEMINI_API_KEY, LLM_PROVIDER, OPENAI_API_KEY


class LLMExplainer:
    """Provides human-readable justifications for negotiated recovery plans.
    
    Can query Google Gemini via REST or provide high-fidelity offline heuristic
    trade-off explanations if an API key is not configured.
    """

    def __init__(self, api_key: Optional[str] = None, provider: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", GEMINI_API_KEY)
        self.provider = (provider or LLM_PROVIDER or "gemini").lower()

    def explain_plan(self, disruption: DisruptionEvent, plan: RecoveryPlan) -> str:
        """Generates an executive explanation of why this plan was chosen and trade-offs made."""
        # 1. Attempt live Google Gemini REST API call if key is present
        if self.api_key and self.api_key != "your_gemini_api_key_here":
            try:
                live_explanation = self._call_gemini_explanation(disruption, plan)
                if live_explanation:
                    return live_explanation
            except Exception as e:
                # Log and fallback gracefully without failing the pipeline
                pass

        # 2. High-fidelity deterministic heuristic explanation
        return self._generate_heuristic_explanation(disruption, plan)

    def parse_text_event(self, raw_text: str) -> Dict[str, Any]:
        """Extracts structured disruption signals from unstructured text/emails/SMS."""
        if self.api_key and self.api_key != "your_gemini_api_key_here":
            try:
                live_event = self._call_gemini_parse(raw_text)
                if live_event:
                    return live_event
            except Exception:
                pass

        # Fallback keyword and regex heuristic parser
        return self._heuristic_parse_text(raw_text)

    # ──────────────────────────────────────────────────────────────────
    # Live Gemini REST API Call
    # ──────────────────────────────────────────────────────────────────

    def _call_gemini_explanation(self, disruption: DisruptionEvent, plan: RecoveryPlan) -> Optional[str]:
        """Calls Gemini generateContent endpoint directly via standard HTTP."""
        prompt = PLAN_EXPLANATION_PROMPT.format(
            disruption_details=(
                f"ID: {disruption.event_id}, Type: {disruption.event_type.value}, "
                f"Source: {disruption.source_entity_id}, Delay: {disruption.delay_hours} hrs, "
                f"Description: {disruption.description}"
            ),
            plan_category=plan.category.value,
            total_cost_inr=f"{plan.total_cost_inr:,.2f}",
            delay_hours=f"{plan.total_delay_hours:.1f}",
            reliability_score=f"{plan.reliability_score * 100:.0f}%",
            cost_breakdown=json.dumps(plan.cost_breakdown or {})
        )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 300}
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

        with urllib.request.urlopen(req, timeout=5) as response:
            result = json.loads(response.read().decode("utf-8"))
            candidates = result.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text", "").strip()
        return None

    def _call_gemini_parse(self, raw_text: str) -> Optional[Dict[str, Any]]:
        """Calls Gemini API to parse text into structured JSON event."""
        prompt = f"{TEXT_TO_EVENT_PROMPT}\nText: \"{raw_text}\"\nOutput valid JSON only."
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.0, "responseMimeType": "application/json"}
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

        with urllib.request.urlopen(req, timeout=5) as response:
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

        if cat == PlanCategory.CHEAPEST:
            return (
                f"🟢 [Cheapest Plan Analysis]: Prioritizes cost containment ({cost}) by absorbing the "
                f"{disruption.delay_hours:.1f}h port delay. The carrier driver waits rather than deploying "
                f"an expensive replacement fleet, and dock intake is deferred to standard shift hours. "
                f"Projected delay is +{delay}h with {rel} reliability. Recommended when cargo is not "
                f"time-critical and SLA penalties are low."
            )
        elif cat == PlanCategory.FASTEST:
            return (
                f"⚡ [Fastest Plan Analysis]: Maximizes delivery velocity, reducing added delay to just "
                f"+{delay}h (vs nominal +{disruption.delay_hours:.1f}h cascade). Authorizes priority crane "
                f"handling at {plan.port_slot_id} and hot-dispatches a backup truck fleet. Total cost is {cost} "
                f"at {rel} reliability. Recommended to avoid severe downstream customer contract SLA fines."
            )
        else:  # SAFEST
            return (
                f"🛡️ [Safest Plan Analysis]: Optimal balanced compromise achieving highest operational stability "
                f"({rel} reliability). Realigns trucking with a confirmed buffer window and reserves protected dock intake. "
                f"Total recovery cost is {cost} with +{delay}h transit offset. Recommended for high-value freight "
                f"to eliminate compounding bottleneck risks."
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

        # Simple hour extraction
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
