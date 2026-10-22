"""Shared Pydantic data schemas defining standardized contracts across all modules."""

from enum import Enum
from typing import List, Dict, Optional, Any
from datetime import datetime
try:
    from pydantic import BaseModel, Field, model_validator
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
    def model_validator(mode="before"):
        def decorator(fn):
            return fn
        return decorator


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
    is_high_risk: bool = False
    predicted_delay_hours: float = 0.0
    key_factors: List[str] = Field(default_factory=list)
    risk_level: Optional[str] = None
    features_used: Dict[str, float] = Field(default_factory=dict)


class CascadeNode(BaseModel):
    """Represents an operational node in the logistics journey."""
    node_id: str = Field(..., description="Unique node identifier (e.g. PORT_BERTH, TRUCK_PICKUP)")
    node_type: str = Field(..., description="Type of node: PORT, TRUCK, WAREHOUSE, CUSTOMER")
    name: str = Field(..., description="Human-readable node label")
    status: str = Field(..., description="Operational status: ON_TIME, DELAYED, BREACHED, CRITICAL")
    scheduled_time: Optional[str] = Field(None, description="ISO timestamp of scheduled event")
    actual_or_projected_time: Optional[str] = Field(None, description="ISO timestamp of projected/actual event")
    delay_hours: float = Field(0.0, description="Accumulated or propagated delay in hours at this node")
    details: Dict[str, Any] = Field(default_factory=dict, description="Node-specific operational telemetry and metrics")


class CascadeEdge(BaseModel):
    """Represents a directional handoff or transit dependency between nodes."""
    source: str = Field(..., description="Source node ID")
    target: str = Field(..., description="Target node ID")
    edge_type: str = Field(..., description="Type of relationship: BERTH_TO_TRUCK, TRUCK_TRANSIT, WAREHOUSE_TO_CUSTOMER")
    delay_propagated_hours: float = Field(0.0, description="Delay transferred across this dependency link in hours")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Edge metadata such as buffer or transit duration")


class CascadeImpact(BaseModel):
    """Comprehensive impact analysis across the supply chain disruption graph."""
    # Common original fields
    disruption_event_id: str = ""
    affected_nodes: List[str] = Field(default_factory=list)
    affected_booking_ids: List[str] = Field(default_factory=list)
    total_financial_risk_inr: float = Field(default=0.0, description="Downstream ₹ at risk")
    downstream_delay_hours: float = 0.0
    critical_path: List[str] = Field(default_factory=list)

    # Deliverable 2 cascade impact attributes
    shipment_id: Optional[str] = None
    initial_delay_hours: float = 0.0
    total_cascaded_delay_hours: float = 0.0
    financial_risk_inr: float = 0.0
    risk_level: str = "LOW"
    penalty_breakdown: Dict[str, float] = Field(default_factory=dict)
    nodes: List[CascadeNode] = Field(default_factory=list)
    edges: List[CascadeEdge] = Field(default_factory=list)
    summary: str = ""

    def __init__(self, **data):
        # Synchronize dual fields for seamless interoperability
        if "financial_risk_inr" in data and "total_financial_risk_inr" not in data:
            data["total_financial_risk_inr"] = data["financial_risk_inr"]
        elif "total_financial_risk_inr" in data and "financial_risk_inr" not in data:
            data["financial_risk_inr"] = data["total_financial_risk_inr"]

        if "total_cascaded_delay_hours" in data and "downstream_delay_hours" not in data:
            data["downstream_delay_hours"] = data["total_cascaded_delay_hours"]
        elif "downstream_delay_hours" in data and "total_cascaded_delay_hours" not in data:
            data["total_cascaded_delay_hours"] = data["downstream_delay_hours"]

        if "shipment_id" in data and not data.get("disruption_event_id"):
            data["disruption_event_id"] = f"EVT-{data['shipment_id']}"

        if "nodes" in data and not data.get("affected_nodes"):
            data["affected_nodes"] = [getattr(n, "node_id", n.get("node_id") if isinstance(n, dict) else str(n)) for n in data["nodes"]]

        super().__init__(**data)


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
