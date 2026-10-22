"""Warehouse Agent managing loading bay availability, labor shifts, and overtime penalties."""

from datetime import datetime, timedelta
from typing import Dict, Any
from src.agents.base_agent import BaseAgent
from src.common.schemas import AgentRole, AgentOffer, DisruptionEvent


class WarehouseAgent(BaseAgent):
    """Represents distribution center / destination warehouse."""

    def __init__(self, agent_id: str = "WAREHOUSE_DC_SOUTH"):
        super().__init__(agent_id, AgentRole.WAREHOUSE)
        self.overtime_labor_rate = 600.0  # INR per hour
        self.dock_slot_fee = 2000.0

    def evaluate_disruption(self, disruption: DisruptionEvent) -> Dict[str, Any]:
        return {"dock_status": "busy", "shift_end_hours": 5.0}

    def generate_initial_offer(self, round_num: int, context: Dict[str, Any]) -> AgentOffer:
        # TODO: Propose dock intake slot
        now = datetime.utcnow()
        return AgentOffer(
            agent_id=self.agent_id,
            agent_role=self.role,
            round_number=round_num,
            slot_id="DOCK_BAY_04",
            proposed_start_time=now + timedelta(hours=5),
            proposed_end_time=now + timedelta(hours=8),
            cost_inr=2800.0,
            reliability_score=0.95,
            constraints_met=True
        )

    def generate_counter_offer(self, round_num: int, coordinator_feedback: Dict[str, Any]) -> AgentOffer:
        # TODO: Reallocate bays or factor in overtime wages
        return self.generate_initial_offer(round_num, coordinator_feedback)

    def calculate_internal_cost(self, proposed_slot: Dict[str, Any]) -> float:
        return 2800.0
