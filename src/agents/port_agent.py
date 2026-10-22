"""Port Agent managing container terminal berth windows, gate queues, and demurrage."""

from datetime import datetime, timedelta
from typing import Dict, Any
from src.agents.base_agent import BaseAgent
from src.common.schemas import AgentRole, AgentOffer, DisruptionEvent


class PortAgent(BaseAgent):
    """Represents maritime container terminal / port operator."""

    def __init__(self, agent_id: str = "PORT_TERMINAL_A"):
        super().__init__(agent_id, AgentRole.PORT)
        self.berth_reschedule_fee = 1200.0  # INR

    def evaluate_disruption(self, disruption: DisruptionEvent) -> Dict[str, Any]:
        return {"berth_occupancy": "congested", "next_available_slot_hrs": 3.0}

    def generate_initial_offer(self, round_num: int, context: Dict[str, Any]) -> AgentOffer:
        # TODO: Implement berth window proposal
        now = datetime.utcnow()
        return AgentOffer(
            agent_id=self.agent_id,
            agent_role=self.role,
            round_number=round_num,
            slot_id="BERTH_WINDOW_B2",
            proposed_start_time=now + timedelta(hours=1),
            proposed_end_time=now + timedelta(hours=4),
            cost_inr=5000.0,
            reliability_score=0.88,
            constraints_met=True
        )

    def generate_counter_offer(self, round_num: int, coordinator_feedback: Dict[str, Any]) -> AgentOffer:
        # TODO: Reschedule berth/gate window based on negotiation round
        return self.generate_initial_offer(round_num, coordinator_feedback)

    def calculate_internal_cost(self, proposed_slot: Dict[str, Any]) -> float:
        return 5000.0
