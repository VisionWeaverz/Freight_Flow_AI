# Shared API Contracts & Integration Guide

All subsystems communicate through strictly typed data contracts defined in `src/common/schemas.py`. By adhering to these schemas, each module can be developed independently using mock inputs and outputs.

---

## 1. Disruption Ingestion Contract

```python
class DisruptionEvent(BaseModel):
    event_id: str
    event_type: DisruptionType       # PORT_CONGESTION, TRUCK_BREAKDOWN, etc.
    source_entity_id: str            # e.g., "PORT_JNPT_BERTH_2"
    severity_level: float            # 0.0 to 1.0
    delay_hours: float               # e.g., 4.0
    reported_at: datetime
    description: str
    metadata: Dict[str, Any]
```

---

## 2. Cascade Impact Output Contract

```python
class CascadeImpact(BaseModel):
    disruption_event_id: str
    affected_nodes: List[str]
    affected_booking_ids: List[str]
    total_financial_risk_inr: float  # Downstream ₹ at risk
    downstream_delay_hours: float
    critical_path: List[str]
```

---

## 3. Agent Offer Contract

```python
class AgentOffer(BaseModel):
    agent_id: str
    agent_role: AgentRole            # CARRIER, PORT, WAREHOUSE
    round_number: int                # 1, 2, or 3
    slot_id: str
    proposed_start_time: datetime
    proposed_end_time: datetime
    cost_inr: float
    reliability_score: float         # 0.0 to 1.0
    constraints_met: bool
    notes: Optional[str]
```

---

## 4. Final Recovery Plan Contract

```python
class RecoveryPlan(BaseModel):
    plan_id: str
    category: PlanCategory           # CHEAPEST, FASTEST, SAFEST
    carrier_slot_id: str
    port_slot_id: str
    warehouse_slot_id: str
    total_cost_inr: float
    total_delay_hours: float
    reliability_score: float
    cost_breakdown: Dict[str, float]
    negotiation_rounds_taken: int
    is_feasible: bool
    llm_explanation: Optional[str]
```

---

## 5. Benchmark Metrics Contract

```python
class EvaluationMetrics(BaseModel):
    run_id: int
    baseline_delay_hours: float
    freightflow_delay_hours: float
    delay_reduction_pct: float
    truck_waiting_time_hours: float
    transport_cost_inr: float
    conflicts_resolved: int
```
