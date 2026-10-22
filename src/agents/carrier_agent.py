"""Carrier Agent managing truck fleet constraints, waiting times, and transport costs."""

from datetime import datetime, timedelta
from typing import Dict, Any
from src.agents.base_agent import BaseAgent
from src.common.schemas import AgentRole, AgentOffer, DisruptionEvent


class CarrierAgent(BaseAgent):
    """Represents trucking carrier; optimizes trip cost, driver duty limits, and hourly waiting cost."""

    def __init__(self, agent_id: str = "CARRIER_MAIN"):
        super().__init__(agent_id, AgentRole.CARRIER)
        self.waiting_cost_per_hour = 450.0  # INR per hour
        self.driver_max_hours = 10.0

    def evaluate_disruption(self, disruption: DisruptionEvent) -> Dict[str, Any]:
        return {"carrier_status": "delayed", "additional_wait_hours": disruption.delay_hours}

    def generate_initial_offer(self, round_num: int, context: Dict[str, Any]) -> AgentOffer:
        # TODO: Implement carrier slot proposal
        now = datetime.utcnow()
        return AgentOffer(
            agent_id=self.agent_id,
            agent_role=self.role,
            round_number=round_num,
            slot_id="TRUCK_SLOT_01",
            proposed_start_time=now + timedelta(hours=2),
            proposed_end_time=now + timedelta(hours=6),
            cost_inr=3500.0,
            reliability_score=0.92,
            constraints_met=True
        )

    def generate_counter_offer(self, round_num: int, coordinator_feedback: Dict[str, Any]) -> AgentOffer:
        # TODO: Adjust offer in response to port and warehouse feedback
        return self.generate_initial_offer(round_num, coordinator_feedback)

    def calculate_internal_cost(self, proposed_slot: Dict[str, Any]) -> float:
        return 3500.0
