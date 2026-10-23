"""Carrier Agent managing truck fleet constraints, waiting times, and transport costs."""

from datetime import datetime, timedelta
from typing import Dict, Any, List
from src.agents.base_agent import BaseAgent
from src.common.schemas import AgentRole, AgentOffer, DisruptionEvent


# Business constants ────────────────────────────────────────────────
REPLACEMENT_TRUCK_FLAT_COST_INR = 4500.0   # Fixed cost for a fresh replacement truck
REPLACEMENT_TRUCK_WAIT_HOURS = 0.0         # Replacement truck has no waiting time
REPLACEMENT_RELIABILITY = 0.85             # Slightly lower — unfamiliar driver/route
WAITING_RELIABILITY = 0.91                 # Original driver, familiar route


class CarrierAgent(BaseAgent):
    """Represents a trucking carrier; optimises trip cost, driver duty limits, and waiting cost.

    On receiving a disruption the agent evaluates two alternatives:

    Option A — **Wait with current driver**: the driver waits at the berth.
    Cost = driver_rate (from context) × wait_hours.  When no driver rate is
    supplied via context, the instance default (₹500/hr) is used.

    Option B — **Replacement truck**: dispatch a fresh truck immediately at
    a flat cost of ₹4,500 with zero additional waiting time.

    The cheaper option is surfaced first in ``get_alternatives()``.
    """

    DEFAULT_DRIVER_RATE_PER_HR = 500.0  # ₹ per hour — matches SHP-1005 seed data

    def __init__(self, agent_id: str = "CARRIER_MAIN"):
        super().__init__(agent_id, AgentRole.CARRIER)
        self.driver_rate_per_hr = self.DEFAULT_DRIVER_RATE_PER_HR
        self.replacement_cost = REPLACEMENT_TRUCK_FLAT_COST_INR

    # ──────────────────────────────────────────────────────────────────
    # BaseAgent contract
    # ──────────────────────────────────────────────────────────────────

    def evaluate_disruption(self, disruption: DisruptionEvent) -> Dict[str, Any]:
        """Returns the two carrier recovery alternatives for this disruption."""
        if disruption.delay_hours < 0:
            raise ValueError(
                f"CarrierAgent: delay_hours must be >= 0, got {disruption.delay_hours}"
            )
        return {
            "alternatives": self.get_alternatives(disruption),
            "carrier_status": "WAITING" if disruption.delay_hours > 0 else "ON_TIME",
            "wait_hours": disruption.delay_hours,
        }

    def generate_initial_offer(self, round_num: int, context: Dict[str, Any]) -> AgentOffer:
        """Round 1: offer the cheaper of the two alternatives.

        Cost comparison:
          waiting_cost = driver_rate × wait_hours
          replacement  = ₹4,500 (flat)

        If replacement is cheaper (or equal), prefer it because it also
        eliminates driver fatigue risk.
        """
        wait_hrs = float(context.get("delay_hours", 0.0))
        driver_rate = float(context.get("driver_rate_per_hr", self.driver_rate_per_hr))

        if wait_hrs < 0:
            raise ValueError(
                f"CarrierAgent: context 'delay_hours' must be >= 0, got {wait_hrs}"
            )

        waiting_cost = self.calculate_internal_cost(
            {"delay_hours": wait_hrs, "option": "wait", "driver_rate_per_hr": driver_rate}
        )
        replacement_cost = self.calculate_internal_cost(
            {"delay_hours": wait_hrs, "option": "replace"}
        )

        now = context.get("reference_time", datetime.utcnow())

        if replacement_cost <= waiting_cost:
            slot_start = now  # replacement available immediately
            slot_end = slot_start + timedelta(hours=4)
            return AgentOffer(
                agent_id=self.agent_id,
                agent_role=self.role,
                round_number=round_num,
                slot_id=f"TRUCK-REPLACEMENT-R{round_num}",
                proposed_start_time=slot_start,
                proposed_end_time=slot_end,
                cost_inr=replacement_cost,
                reliability_score=REPLACEMENT_RELIABILITY,
                constraints_met=True,
                notes=(
                    f"Replacement truck (flat ₹{replacement_cost:,.0f}) is cheaper "
                    f"than driver wait cost (₹{waiting_cost:,.0f} = "
                    f"₹{driver_rate:.0f}/hr × {wait_hrs:.1f} hrs)."
                ),
            )
        else:
            slot_start = now + timedelta(hours=wait_hrs)
            slot_end = slot_start + timedelta(hours=4)
            return AgentOffer(
                agent_id=self.agent_id,
                agent_role=self.role,
                round_number=round_num,
                slot_id=f"TRUCK-WAIT-R{round_num}",
                proposed_start_time=slot_start,
                proposed_end_time=slot_end,
                cost_inr=waiting_cost,
                reliability_score=WAITING_RELIABILITY,
                constraints_met=True,
                notes=(
                    f"Current driver waits {wait_hrs:.1f} hrs × ₹{driver_rate:.0f}/hr "
                    f"= ₹{waiting_cost:,.0f}. Cheaper than replacement (₹{replacement_cost:,.0f})."
                ),
            )

    def generate_counter_offer(
        self, round_num: int, coordinator_feedback: Dict[str, Any]
    ) -> AgentOffer:
        """Round 2/3: if coordinator prefers speed, offer replacement; otherwise offer wait."""
        prefer_fast = coordinator_feedback.get("prefer_fast", False)
        if prefer_fast:
            wait_hrs = float(coordinator_feedback.get("delay_hours", 0.0))
            now = coordinator_feedback.get("reference_time", datetime.utcnow())
            cost = self.calculate_internal_cost(
                {"delay_hours": wait_hrs, "option": "replace"}
            )
            return AgentOffer(
                agent_id=self.agent_id,
                agent_role=self.role,
                round_number=round_num,
                slot_id=f"TRUCK-REPLACEMENT-R{round_num}",
                proposed_start_time=now,
                proposed_end_time=now + timedelta(hours=4),
                cost_inr=cost,
                reliability_score=REPLACEMENT_RELIABILITY,
                constraints_met=True,
                notes="Replacement truck preferred for speed.",
            )
        return self.generate_initial_offer(round_num, coordinator_feedback)

    def calculate_internal_cost(self, proposed_slot: Dict[str, Any]) -> float:
        """Computes carrier cost from the proposed slot dictionary.

        Args:
            proposed_slot: Must contain:
                - 'option' (str): 'wait' or 'replace'
                - 'delay_hours' (float): hours of driver waiting
                - 'driver_rate_per_hr' (float, optional): override per-hour rate

        Returns:
            Total ₹ cost (rounded to 2 dp).

        Raises:
            ValueError: if 'option' is missing/invalid, or 'delay_hours' is
                        missing or negative.
        """
        if "option" not in proposed_slot:
            raise ValueError("CarrierAgent.calculate_internal_cost: 'option' is required.")
        option = proposed_slot["option"]
        if option not in ("wait", "replace"):
            raise ValueError(
                f"CarrierAgent.calculate_internal_cost: 'option' must be 'wait' or 'replace', "
                f"got '{option}'."
            )
        if "delay_hours" not in proposed_slot:
            raise ValueError("CarrierAgent.calculate_internal_cost: 'delay_hours' is required.")
        delay_hrs = float(proposed_slot["delay_hours"])
        if delay_hrs < 0:
            raise ValueError(
                f"CarrierAgent.calculate_internal_cost: 'delay_hours' must be >= 0, "
                f"got {delay_hrs}."
            )
        if option == "replace":
            return round(REPLACEMENT_TRUCK_FLAT_COST_INR, 2)
        # option == "wait"
        rate = float(proposed_slot.get("driver_rate_per_hr", self.driver_rate_per_hr))
        return round(rate * delay_hrs, 2)

    # ──────────────────────────────────────────────────────────────────
    # Public helper — used by the coordinator for plan synthesis
    # ──────────────────────────────────────────────────────────────────

    def get_alternatives(
        self,
        disruption: DisruptionEvent,
        driver_rate_per_hr: float = DEFAULT_DRIVER_RATE_PER_HR,
    ) -> List[Dict[str, Any]]:
        """Returns the two carrier recovery alternatives as plain dicts.

        Alternative A — Wait with current driver:
          • wait_hours = disruption.delay_hours
          • cost = driver_rate × wait_hours

        Alternative B — Replacement truck:
          • wait_hours = 0 (leaves immediately)
          • cost = ₹4,500 flat
        """
        d = disruption.delay_hours
        waiting_cost = self.calculate_internal_cost(
            {"option": "wait", "delay_hours": d, "driver_rate_per_hr": driver_rate_per_hr}
        )
        replacement_cost = self.calculate_internal_cost(
            {"option": "replace", "delay_hours": d}
        )
        return [
            {
                "option": "A",
                "label": "Wait with Current Driver",
                "slot_id": "TRUCK-WAIT",
                "wait_hours": d,
                "cost_inr": waiting_cost,
                "reliability_score": WAITING_RELIABILITY,
            },
            {
                "option": "B",
                "label": "Replacement Truck (Flat Rate)",
                "slot_id": "TRUCK-REPLACEMENT",
                "wait_hours": REPLACEMENT_TRUCK_WAIT_HOURS,
                "cost_inr": replacement_cost,
                "reliability_score": REPLACEMENT_RELIABILITY,
            },
        ]
