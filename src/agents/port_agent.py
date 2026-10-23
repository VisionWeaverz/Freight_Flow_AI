"""Port Agent managing container terminal berth windows, gate queues, and demurrage."""

from datetime import datetime, timedelta
from typing import Dict, Any, List
from src.agents.base_agent import BaseAgent
from src.common.schemas import AgentRole, AgentOffer, DisruptionEvent


# Business constants ────────────────────────────────────────────────
EXPEDITED_HANDLING_RATE_PER_HR = 1500.0  # ₹ per hour of port delay absorbed
ALTERNATIVE_SLOT_EXTRA_DELAY_HRS = 2.0   # Additional buffer for the later slot
BASE_BERTH_FEE_INR = 1200.0              # Fixed gate/berth administration fee
EXPEDITED_RELIABILITY = 0.82             # Slightly lower — compressed schedule
DEFERRED_RELIABILITY = 0.93             # More time = higher confidence


class PortAgent(BaseAgent):
    """Represents a maritime container terminal / port operator.

    On receiving a disruption the agent evaluates two alternatives:

    Option A — **Delayed current slot**: honour the existing berth with a
    delay equal to the disruption delay.  Cost = base berth fee only (no
    expediting).  Reliability reflects the congestion-induced uncertainty.

    Option B — **Expedited alternative slot**: clear the existing queue via
    expedited crane/gate handling at ₹1,500/hr for the delay hours, then
    open a fresh slot 2 hours later than Option A.  Higher cost but faster
    effective clearance and a cleaner schedule.

    The agent uses the disruption context passed in `context` so decisions
    are deterministic and require no DB access.  Invalid inputs (negative
    delay, missing keys) raise ``ValueError`` explicitly rather than
    silently fabricating data.
    """

    def __init__(self, agent_id: str = "PORT_TERMINAL_A"):
        super().__init__(agent_id, AgentRole.PORT)
        self.expedited_rate = EXPEDITED_HANDLING_RATE_PER_HR
        self.base_fee = BASE_BERTH_FEE_INR

    # ──────────────────────────────────────────────────────────────────
    # BaseAgent contract
    # ──────────────────────────────────────────────────────────────────

    def evaluate_disruption(self, disruption: DisruptionEvent) -> Dict[str, Any]:
        """Returns the two port recovery alternatives for this disruption."""
        if disruption.delay_hours < 0:
            raise ValueError(
                f"PortAgent: delay_hours must be >= 0, got {disruption.delay_hours}"
            )
        return {
            "alternatives": self.get_alternatives(disruption),
            "berth_status": "CONGESTED" if disruption.severity_level >= 0.5 else "MODERATE",
            "delay_hours": disruption.delay_hours,
        }

    def generate_initial_offer(self, round_num: int, context: Dict[str, Any]) -> AgentOffer:
        """Round 1: offer the delayed current berth slot (Option A — lower cost)."""
        delay_hrs = float(context.get("delay_hours", 0.0))
        if delay_hrs < 0:
            raise ValueError(f"PortAgent: context 'delay_hours' must be >= 0, got {delay_hrs}")

        now = context.get("reference_time", datetime.utcnow())
        slot_start = now + timedelta(hours=delay_hrs)
        slot_end = slot_start + timedelta(hours=3)
        cost = self.calculate_internal_cost({"delay_hours": delay_hrs, "expedited": False})

        return AgentOffer(
            agent_id=self.agent_id,
            agent_role=self.role,
            round_number=round_num,
            slot_id=f"BERTH-DELAYED-R{round_num}",
            proposed_start_time=slot_start,
            proposed_end_time=slot_end,
            cost_inr=cost,
            reliability_score=DEFERRED_RELIABILITY,
            constraints_met=True,
            notes=(
                f"Delayed current berth slot: +{delay_hrs:.1f} hrs. "
                f"Base fee only (₹{cost:,.0f})."
            ),
        )

    def generate_counter_offer(
        self, round_num: int, coordinator_feedback: Dict[str, Any]
    ) -> AgentOffer:
        """Round 2/3: propose the expedited alternative slot (Option B — faster).

        If the coordinator signals cost pressure ('prefer_cheap': True), the agent
        falls back to Option A.  Otherwise it offers the expedited slot.
        """
        delay_hrs = float(coordinator_feedback.get("delay_hours", 0.0))
        prefer_cheap = coordinator_feedback.get("prefer_cheap", False)
        now = coordinator_feedback.get("reference_time", datetime.utcnow())

        if prefer_cheap:
            return self.generate_initial_offer(round_num, coordinator_feedback)

        # Expedited slot starts 2 hours after the delayed berth time
        extra = ALTERNATIVE_SLOT_EXTRA_DELAY_HRS
        slot_start = now + timedelta(hours=delay_hrs + extra)
        slot_end = slot_start + timedelta(hours=3)
        cost = self.calculate_internal_cost(
            {"delay_hours": delay_hrs, "expedited": True}
        )

        return AgentOffer(
            agent_id=self.agent_id,
            agent_role=self.role,
            round_number=round_num,
            slot_id=f"BERTH-EXPEDITED-R{round_num}",
            proposed_start_time=slot_start,
            proposed_end_time=slot_end,
            cost_inr=cost,
            reliability_score=EXPEDITED_RELIABILITY,
            constraints_met=True,
            notes=(
                f"Expedited berth +{delay_hrs + extra:.1f} hrs from now. "
                f"Expediting cost ₹{self.expedited_rate:.0f}/hr × {delay_hrs:.1f} hrs "
                f"= ₹{self.expedited_rate * delay_hrs:,.0f} + base ₹{self.base_fee:.0f} "
                f"= ₹{cost:,.0f}."
            ),
        )

    def calculate_internal_cost(self, proposed_slot: Dict[str, Any]) -> float:
        """Computes port cost from the proposed slot dictionary.

        Args:
            proposed_slot: Must contain 'delay_hours' (float) and optionally
                'expedited' (bool, default False).

        Returns:
            Total ₹ cost.

        Raises:
            ValueError: if 'delay_hours' is missing or negative.
        """
        if "delay_hours" not in proposed_slot:
            raise ValueError("PortAgent.calculate_internal_cost: 'delay_hours' is required.")
        delay_hrs = float(proposed_slot["delay_hours"])
        if delay_hrs < 0:
            raise ValueError(
                f"PortAgent.calculate_internal_cost: 'delay_hours' must be >= 0, got {delay_hrs}"
            )
        expedited = bool(proposed_slot.get("expedited", False))
        expediting_cost = self.expedited_rate * delay_hrs if expedited else 0.0
        return round(self.base_fee + expediting_cost, 2)

    # ──────────────────────────────────────────────────────────────────
    # Public helper — used by the coordinator for plan synthesis
    # ──────────────────────────────────────────────────────────────────

    def get_alternatives(self, disruption: DisruptionEvent) -> List[Dict[str, Any]]:
        """Returns the two port recovery alternatives as plain dicts.

        These are consumed by ``CentralCoordinator`` when assembling
        Cheapest / Fastest / Safest plans.

        Alternative A — Delayed current slot (lower cost, moderate delay):
          • delay added = disruption.delay_hours
          • cost = base fee (₹1,200), no expediting

        Alternative B — Expedited later slot (higher cost, stable schedule):
          • delay added = disruption.delay_hours + 2 hrs
          • cost = base fee + ₹1,500 × delay_hours
        """
        d = disruption.delay_hours
        cost_a = self.calculate_internal_cost({"delay_hours": d, "expedited": False})
        cost_b = self.calculate_internal_cost({"delay_hours": d, "expedited": True})

        return [
            {
                "option": "A",
                "label": "Delayed Current Slot",
                "slot_id": "BERTH-DELAYED",
                "added_delay_hours": d,
                "cost_inr": cost_a,
                "reliability_score": DEFERRED_RELIABILITY,
            },
            {
                "option": "B",
                "label": "Expedited Alternative Slot",
                "slot_id": "BERTH-EXPEDITED",
                "added_delay_hours": d + ALTERNATIVE_SLOT_EXTRA_DELAY_HRS,
                "cost_inr": cost_b,
                "reliability_score": EXPEDITED_RELIABILITY,
            },
        ]
