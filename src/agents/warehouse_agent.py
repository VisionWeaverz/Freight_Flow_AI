"""Warehouse Agent managing loading bay availability, labor shifts, and overtime penalties."""

from datetime import datetime, timedelta
from typing import Dict, Any, List
from src.agents.base_agent import BaseAgent
from src.common.schemas import AgentRole, AgentOffer, DisruptionEvent


# Business constants ────────────────────────────────────────────────
EVENING_OVERTIME_RATE_PER_HR = 1500.0    # ₹ per hour of evening overtime labor
NEXT_MORNING_HOLDING_FEE_INR = 3000.0   # ₹ flat holding fee for next-morning slot
NEXT_MORNING_OVERTIME_HRS = 0.0         # No overtime — fresh morning shift
NEXT_MORNING_SLOT_HOUR = 8               # Slot 1 opens at 08:00 AM next day
NEXT_MORNING_SLOT_OFFSET_HRS = 14.0     # Legacy constant preserved for compatibility

OVERTIME_RELIABILITY = 0.80             # Evening crew; fatigue/error risk higher
NEXT_MORNING_RELIABILITY = 0.97         # Full day-shift; highest confidence


def compute_next_morning_slot(ref_time: datetime) -> datetime:
    """Calculates the 08:00 AM slot on the next calendar day.

    Preserves timezone information if present.
    Whether requested in the morning (09:00), evening (18:00), or late night (23:00),
    the next morning slot is always 08:00 on the following calendar day (day D + 1).
    """
    next_day = ref_time + timedelta(days=1)
    return next_day.replace(
        hour=NEXT_MORNING_SLOT_HOUR, minute=0, second=0, microsecond=0
    )


class WarehouseAgent(BaseAgent):
    """Represents a distribution centre / destination warehouse.

    On receiving a disruption the agent evaluates two alternatives:

    Option A — **Evening overtime**: the current dock bay absorbs the delay
    using overtime labor at ₹1,500 per hour for the extra hours incurred.

    Option B — **Next-morning Slot 1**: defer intake entirely to the first
    morning slot the next day.  Incurs a flat ₹3,000 holding fee but zero
    overtime cost and much higher reliability.

    The agent reads ``delay_hours`` from context so decisions are
    deterministic and do not depend on the local clock.
    """

    def __init__(self, agent_id: str = "WAREHOUSE_DC_SOUTH"):
        super().__init__(agent_id, AgentRole.WAREHOUSE)
        self.overtime_rate = EVENING_OVERTIME_RATE_PER_HR
        self.holding_fee = NEXT_MORNING_HOLDING_FEE_INR

    # ──────────────────────────────────────────────────────────────────
    # BaseAgent contract
    # ──────────────────────────────────────────────────────────────────

    def evaluate_disruption(self, disruption: DisruptionEvent) -> Dict[str, Any]:
        """Returns the two warehouse recovery alternatives for this disruption."""
        if disruption.delay_hours < 0:
            raise ValueError(
                f"WarehouseAgent: delay_hours must be >= 0, got {disruption.delay_hours}"
            )
        return {
            "alternatives": self.get_alternatives(disruption),
            "dock_status": "OVERTIME_NEEDED" if disruption.delay_hours > 0 else "ON_TIME",
            "delay_hours": disruption.delay_hours,
        }

    def generate_initial_offer(self, round_num: int, context: Dict[str, Any]) -> AgentOffer:
        """Round 1: offer the cheaper of the two alternatives.

        If overtime total <= holding fee, prefer overtime (Option A) to
        minimise delay.  Otherwise prefer the next-morning slot (Option B).
        """
        delay_hrs = float(context.get("delay_hours", 0.0))
        if delay_hrs < 0:
            raise ValueError(
                f"WarehouseAgent: context 'delay_hours' must be >= 0, got {delay_hrs}"
            )
        now = context.get("reference_time", datetime.utcnow())

        overtime_cost = self.calculate_internal_cost(
            {"option": "overtime", "delay_hours": delay_hrs}
        )
        morning_cost = self.calculate_internal_cost(
            {"option": "morning", "delay_hours": delay_hrs}
        )

        if overtime_cost <= morning_cost:
            slot_start = now + timedelta(hours=delay_hrs)
            slot_end = slot_start + timedelta(hours=3)
            return AgentOffer(
                agent_id=self.agent_id,
                agent_role=self.role,
                round_number=round_num,
                slot_id=f"DOCK-OVERTIME-R{round_num}",
                proposed_start_time=slot_start,
                proposed_end_time=slot_end,
                cost_inr=overtime_cost,
                reliability_score=OVERTIME_RELIABILITY,
                constraints_met=True,
                notes=(
                    f"Evening overtime: {delay_hrs:.1f} hrs × ₹{self.overtime_rate:,.0f}/hr "
                    f"= ₹{overtime_cost:,.0f}. Cheaper than next-morning (₹{morning_cost:,.0f})."
                ),
            )
        else:
            slot_start = compute_next_morning_slot(now)
            slot_end = slot_start + timedelta(hours=3)
            return AgentOffer(
                agent_id=self.agent_id,
                agent_role=self.role,
                round_number=round_num,
                slot_id=f"DOCK-MORNING-R{round_num}",
                proposed_start_time=slot_start,
                proposed_end_time=slot_end,
                cost_inr=morning_cost,
                reliability_score=NEXT_MORNING_RELIABILITY,
                constraints_met=True,
                notes=(
                    f"Next-morning Slot 1 (₹{morning_cost:,.0f} holding fee, "
                    f"0 overtime). Overtime would cost ₹{overtime_cost:,.0f}."
                ),
            )

    def generate_counter_offer(
        self, round_num: int, coordinator_feedback: Dict[str, Any]
    ) -> AgentOffer:
        """Round 2/3: if coordinator prefers reliability, offer morning slot; if prefer_fast, offer overtime."""
        prefer_reliable = coordinator_feedback.get("prefer_reliable", False)
        prefer_fast = coordinator_feedback.get("prefer_fast", False)
        delay_hrs = float(coordinator_feedback.get("delay_hours", 0.0))
        if delay_hrs < 0:
            raise ValueError(
                f"WarehouseAgent: coordinator_feedback 'delay_hours' must be >= 0, got {delay_hrs}"
            )
        now = coordinator_feedback.get("reference_time", datetime.utcnow())

        if prefer_reliable:
            cost = self.calculate_internal_cost(
                {"option": "morning", "delay_hours": delay_hrs}
            )
            slot_start = compute_next_morning_slot(now)
            return AgentOffer(
                agent_id=self.agent_id,
                agent_role=self.role,
                round_number=round_num,
                slot_id=f"DOCK-MORNING-R{round_num}",
                proposed_start_time=slot_start,
                proposed_end_time=slot_start + timedelta(hours=3),
                cost_inr=cost,
                reliability_score=NEXT_MORNING_RELIABILITY,
                constraints_met=True,
                notes="Next-morning Slot 1 preferred for reliability.",
            )
        if prefer_fast:
            cost = self.calculate_internal_cost(
                {"option": "overtime", "delay_hours": delay_hrs}
            )
            slot_start = now + timedelta(hours=delay_hrs)
            return AgentOffer(
                agent_id=self.agent_id,
                agent_role=self.role,
                round_number=round_num,
                slot_id=f"DOCK-OVERTIME-R{round_num}",
                proposed_start_time=slot_start,
                proposed_end_time=slot_start + timedelta(hours=3),
                cost_inr=cost,
                reliability_score=OVERTIME_RELIABILITY,
                constraints_met=True,
                notes="Evening overtime preferred for speed.",
            )
        return self.generate_initial_offer(round_num, coordinator_feedback)

    def calculate_internal_cost(self, proposed_slot: Dict[str, Any]) -> float:
        """Computes warehouse cost from the proposed slot dictionary.

        Args:
            proposed_slot: Must contain:
                - 'option' (str): 'overtime' or 'morning'
                - 'delay_hours' (float): hours of delay triggering overtime

        Returns:
            Total ₹ cost (rounded to 2 dp).

        Raises:
            ValueError: if 'option' is missing/invalid, or 'delay_hours' is
                        missing or negative.
        """
        if "option" not in proposed_slot:
            raise ValueError("WarehouseAgent.calculate_internal_cost: 'option' is required.")
        option = proposed_slot["option"]
        if option not in ("overtime", "morning"):
            raise ValueError(
                f"WarehouseAgent.calculate_internal_cost: 'option' must be 'overtime' or "
                f"'morning', got '{option}'."
            )
        if "delay_hours" not in proposed_slot:
            raise ValueError(
                "WarehouseAgent.calculate_internal_cost: 'delay_hours' is required."
            )
        delay_hrs = float(proposed_slot["delay_hours"])
        if delay_hrs < 0:
            raise ValueError(
                f"WarehouseAgent.calculate_internal_cost: 'delay_hours' must be >= 0, "
                f"got {delay_hrs}."
            )
        if option == "morning":
            return round(NEXT_MORNING_HOLDING_FEE_INR, 2)
        # option == "overtime"
        return round(self.overtime_rate * delay_hrs, 2)

    # ──────────────────────────────────────────────────────────────────
    # Public helper — used by the coordinator for plan synthesis
    # ──────────────────────────────────────────────────────────────────

    def get_alternatives(self, disruption: DisruptionEvent) -> List[Dict[str, Any]]:
        """Returns the two warehouse recovery alternatives as plain dicts.

        Alternative A — Evening overtime:
          • overtime_hours = disruption.delay_hours
          • cost = ₹1,500 × delay_hours

        Alternative B — Next-morning Slot 1:
          • overtime_hours = 0
          • cost = ₹3,000 flat holding fee
        """
        d = disruption.delay_hours
        overtime_cost = self.calculate_internal_cost(
            {"option": "overtime", "delay_hours": d}
        )
        morning_cost = self.calculate_internal_cost(
            {"option": "morning", "delay_hours": d}
        )
        return [
            {
                "option": "A",
                "label": "Evening Overtime",
                "slot_id": "DOCK-OVERTIME",
                "overtime_hours": d,
                "cost_inr": overtime_cost,
                "reliability_score": OVERTIME_RELIABILITY,
            },
            {
                "option": "B",
                "label": "Next-Morning Slot 1",
                "slot_id": "DOCK-MORNING",
                "overtime_hours": NEXT_MORNING_OVERTIME_HRS,
                "cost_inr": morning_cost,
                "reliability_score": NEXT_MORNING_RELIABILITY,
            },
        ]
