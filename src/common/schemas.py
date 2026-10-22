"""Shared Pydantic data schemas defining standardized contracts across all modules."""

from enum import Enum
from typing import List, Dict, Optional, Any
from datetime import datetime
try:
    from pydantic import BaseModel, Field
except ImportError:
    from dataclasses import dataclass, field
    class BaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
        def dict(self):
            return self.__dict__
    def Field(default=None, default_factory=None, description=None, ge=None, le=None):
        if default_factory is not None:
            return field(default_factory=default_factory)
        return field(default=default)


class DisruptionType(str, Enum):
    PORT_CONGESTION = "PORT_CONGESTION"
    VESSEL_DELAY = "VESSEL_DELAY"
    TRUCK_BREAKDOWN = "TRUCK_BREAKDOWN"
    TRAFFIC_INCIDENT = "TRAFFIC_INCIDENT"
    WAREHOUSE_BOTTLENECK = "WAREHOUSE_BOTTLENECK"
    WEATHER_SEVERE = "WEATHER_SEVERE"
    CUSTOMS_HOLD = "CUSTOMS_HOLD"


class PlanCategory(str, Enum):
    CHEAPEST = "CHEAPEST"
    FASTEST = "FASTEST"
    SAFEST = "SAFEST"


class AgentRole(str, Enum):
    CARRIER = "CARRIER"
    PORT = "PORT"
    WAREHOUSE = "WAREHOUSE"
    COORDINATOR = "COORDINATOR"


class DisruptionEvent(BaseModel):
    event_id: str
    event_type: DisruptionType
    source_entity_id: str  # e.g., "PORT_MUMBAI_01", "TRUCK_KA01_2344"
    severity_level: float = Field(ge=0.0, le=1.0, description="0.0 to 1.0 severity")
    delay_hours: float
    reported_at: datetime = Field(default_factory=datetime.utcnow)
    description: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RiskPrediction(BaseModel):
    shipment_id: str
    risk_score: float = Field(ge=0.0, le=1.0, description="Predicted delay risk probability")
    is_high_risk: bool
    predicted_delay_hours: float
    key_factors: List[str] = Field(default_factory=list)


class CascadeImpact(BaseModel):
    disruption_event_id: str
    affected_nodes: List[str]
    affected_booking_ids: List[str]
    total_financial_risk_inr: float = Field(description="Downstream ₹ at risk")
    downstream_delay_hours: float
    critical_path: List[str] = Field(default_factory=list)


class AgentOffer(BaseModel):
    agent_id: str
    agent_role: AgentRole
    round_number: int
    slot_id: str
    proposed_start_time: datetime
    proposed_end_time: datetime
    cost_inr: float
    reliability_score: float = Field(ge=0.0, le=1.0)
    constraints_met: bool
    notes: Optional[str] = None


class RecoveryPlan(BaseModel):
    plan_id: str
    category: PlanCategory  # CHEAPEST, FASTEST, SAFEST
    carrier_slot_id: str
    port_slot_id: str
    warehouse_slot_id: str
    total_cost_inr: float
    total_delay_hours: float
    reliability_score: float
    cost_breakdown: Dict[str, float]
    negotiation_rounds_taken: int
    is_feasible: bool = True
    llm_explanation: Optional[str] = None


class EvaluationMetrics(BaseModel):
    run_id: int
    baseline_delay_hours: float
    freightflow_delay_hours: float
    delay_reduction_pct: float
    truck_waiting_time_hours: float
    transport_cost_inr: float
    conflicts_resolved: int
