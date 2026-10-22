"""Abstract base class for supply chain participant agents."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
from src.common.schemas import AgentRole, AgentOffer, DisruptionEvent


class BaseAgent(ABC):
    """Base class providing negotiation state and constraint interface for agents."""

    def __init__(self, agent_id: str, role: AgentRole):
        self.agent_id = agent_id
        self.role = role
        self.constraints: Dict[str, Any] = {}

    @abstractmethod
    def evaluate_disruption(self, disruption: DisruptionEvent) -> Dict[str, Any]:
        """Assess the disruption impact on internal operations."""
        pass

    @abstractmethod
    def generate_initial_offer(self, round_num: int, context: Dict[str, Any]) -> AgentOffer:
        """Round 1: Initial feasible slot offer."""
        pass

    @abstractmethod
    def generate_counter_offer(self, round_num: int, coordinator_feedback: Dict[str, Any]) -> AgentOffer:
        """Round 2 & 3: Counter-offer adapting to peer constraints."""
        pass

    @abstractmethod
    def calculate_internal_cost(self, proposed_slot: Dict[str, Any]) -> float:
        """Computes internal cost without exposing private margin/operational details."""
        pass
