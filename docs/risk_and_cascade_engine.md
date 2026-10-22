# FreightFlow AI: Risk Classification & Downstream Disruption Cascade Engine

## 1. Overview & Role Scope

This document specifies the technical implementation delivered by the **Data Engineer & Graph Analytics Specialist** for FreightFlow AI. 

The module provides proactive risk identification and downstream propagation modeling for multimodal logistics disruptions across India's freight corridors.

```
+-----------------------------------------------------------------------------------------+
|                                    DISRUPTION INPUT                                     |
|             (e.g., Vessel Berth Delay: +4.0 hours, Port Congestion: 0.75)               |
+--------------------------------------------+--------------------------------------------+
                                             |
                      +----------------------+----------------------+
                      |                                             |
                      v                                             v
+-------------------------------------------+ +-------------------------------------------+
|          1. RISK CLASSIFICATION           | |             2. CASCADE GRAPH              |
|        (src/risk_engine/scorer.py)        | |      (src/cascade/impact_analyzer.py)     |
|                                           | |                                           |
| • GradientBoostingClassifier              | | • NetworkX Directed Acyclic Graph (DAG)   |
| • Features: Congestion, Delay, Value, Rate| | • Path: Port -> Truck -> Whs -> Customer  |
| • Output: Risk Score & Categorical Tier   | | • Computes ₹ at Risk & Penalties          |
|   (LOW | MEDIUM | HIGH | CRITICAL)        | | • Output: CascadeImpact Pydantic Model    |
+---------------------+---------------------+ +---------------------+---------------------+
                      |                                             |
                      +----------------------+----------------------+
                                             |
                                             v
+-----------------------------------------------------------------------------------------+
|                                   DOWNSTREAM CONSUMERS                                  |
|   - Central Coordinator (Agents)  |  Streamlit Ops Dashboard  |  Automated Recovery     |
+-----------------------------------------------------------------------------------------+
```

---

## 2. Shared Data Contract (`src/common/schemas.py`)

The common contract was enhanced to define granular graph topologies while preserving 100% backward compatibility with existing orchestrator and agent schemas.

### 2.1 `CascadeNode`
Represents an operational checkpoint along the freight route:
- `node_id: str`: Unique identifier (`PORT_<id>`, `TRUCK_<id>`, `WHS_<id>`, `CUST_<id>`).
- `node_type: str`: Checkpoint category (`PORT`, `TRUCK`, `WAREHOUSE`, `CUSTOMER`).
- `name: str`: Descriptive checkpoint label with vehicle/driver/facility metadata.
- `status: str`: Operational condition (`ON_TIME`, `DELAYED`, `BREACHED`, `CRITICAL`).
- `scheduled_time: Optional[str]`: Baseline scheduled ISO timestamp.
- `actual_or_projected_time: Optional[str]`: Updated projected arrival or dispatch time.
- `delay_hours: float`: Cumulative or node-level delay in hours.
- `details: Dict[str, Any]`: Telemetry metrics, penalty rates, detention allowances, and buffer thresholds.

### 2.2 `CascadeEdge`
Models physical transit dependencies and handoff constraints:
- `source: str`: Upstream origin node ID.
- `target: str`: Downstream dependent node ID.
- `edge_type: str`: `BERTH_TO_TRUCK_HANDOFF`, `HIGHWAY_TRANSIT`, `FINAL_MILE_FULFILLMENT`.
- `delay_propagated_hours: float`: Transfer delay transmitted across this dependency link.
- `metadata: Dict[str, Any]`: Transit time, buffer windows, and bottleneck flags.

### 2.3 `CascadeImpact`
Standardized response payload representing cumulative disruption:
- `shipment_id: str`: Tracked consignment ID.
- `initial_delay_hours: float`: Upstream disruption origin magnitude.
- `total_cascaded_delay_hours: float`: Final customer-facing delay.
- `financial_risk_inr: float`: Total monetary liability (₹) across all parties.
- `risk_level: str`: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`.
- `penalty_breakdown: Dict[str, float]`: Itemized penalty liabilities.
- `nodes: List[CascadeNode]`: Graph nodes in chronological topological order.
- `edges: List[CascadeEdge]`: Graph dependencies.
- `summary: str`: Plain-English operational briefing.

---

## 3. Risk Classifier Engine (`src/risk_engine/`)

The risk engine predicts disruption probability early, allowing proactive intervention before physical delays ripple downstream.

### 3.1 Feature Pipeline (`feature_pipeline.py`)
Extracts a 4-dimensional normalized feature vector:
1. `historical_delay_rate`: Prior reliability rate of the corridor/carrier ($[0.0, 1.0]$).
2. `port_congestion_index`: Berth and gate utilization indicator ($[0.0, 1.0]$).
3. `delay_hours`: Current observed or projected berth delay (hours).
4. `cargo_value_inr`: Financial invoice value of the freight consignment (₹).

### 3.2 Model Training (`train.py`)
- **Algorithm**: scikit-learn `GradientBoostingClassifier` (`n_estimators=120`, `learning_rate=0.08`, `max_depth=4`, `random_state=42`).
- **Target**: `is_delayed` (binary flag indicating high-severity operational failure).
- **Performance**:
  - Test Accuracy: **83.33%**
  - ROC-AUC: **0.8497**
- **Feature Importances**:
  - `delay_hours`: 45.81%
  - `historical_delay_rate`: 24.77%
  - `port_congestion_index`: 17.36%
  - `cargo_value_inr`: 12.07%
- **Artifact**: Exported to `data/synthetic/risk_model.joblib`.

### 3.3 Inference Scorer (`scorer.py`)
Exposes the required function contract:
```python
predict_risk(shipment_id: str, new_delay_hours: float, congestion: float) -> Tuple[float, str]
```
Returns:
- `risk_score`: Calibrated probability between `0.0` and `1.0`.
- `risk_level`: Categorical risk tier:
  - `score < 0.25`: `LOW`
  - `0.25 <= score < 0.50`: `MEDIUM`
  - `0.50 <= score < 0.75`: `HIGH`
  - `score >= 0.75`: `CRITICAL`

---

## 4. NetworkX Cascade Engine (`src/cascade/`)

The cascade engine evaluates the deterministic ripple effect of an upstream shock across downstream checkpoints using a directed acyclic graph (`nx.DiGraph`).

### 4.1 Dependency Chain Topology
$$\text{Port Berth Arrival Node} \xrightarrow{\text{Handoff}} \text{Truck Pickup Node} \xrightarrow{\text{Transit}} \text{Warehouse Delivery Node} \xrightarrow{\text{Fulfillment}} \text{Customer Promise Node}$$

### 4.2 Penalty Models & Mathematical Formulations

#### 1. Truck Driver Detention Waiting Penalty
Driver scheduled arrival is $T_{\text{pickup}}$. If port berth release is delayed to $T_{\text{berth\_proj}} > T_{\text{pickup}}$:
$$\Delta t_{\text{wait}} = \max\left(0, T_{\text{berth\_proj}} - T_{\text{pickup}}\right)$$

If $\Delta t_{\text{wait}} > t_{\text{max\_wait\_allowed}}$:
$$\text{Penalty}_{\text{driver}} = \Delta t_{\text{wait}} \times C_{\text{wait\_rate\_per\_hr}}$$
The node status transitions to `BREACHED`.

#### 2. Warehouse Dock Slot & Overtime Charges
Given highway transit duration $\tau_{\text{transit}}$:
$$T_{\text{whs\_arrival}} = \max(T_{\text{pickup}}, T_{\text{berth\_proj}}) + \tau_{\text{transit}}$$
$$T_{\text{buffer\_cutoff}} = T_{\text{whs\_slot}} + \Delta t_{\text{buffer\_minutes}}$$

If $T_{\text{whs\_arrival}} > T_{\text{buffer\_cutoff}}$:
$$\text{Penalty}_{\text{missed\_slot}} = C_{\text{missed\_slot\_fixed}}$$
$$\Delta t_{\text{overtime}} = T_{\text{whs\_arrival}} - T_{\text{buffer\_cutoff}}$$
$$\text{Cost}_{\text{overtime}} = \Delta t_{\text{overtime}} \times C_{\text{overtime\_rate\_per\_hr}}$$
The warehouse node status transitions to `BREACHED`.

#### 3. Customer Delivery SLA Breach
$$T_{\text{cust\_delivery}} = T_{\text{whs\_arrival}} + \tau_{\text{dock\_turnaround}}$$

If $T_{\text{cust\_delivery}} > T_{\text{promise}}$:
$$\Delta t_{\text{sla}} = T_{\text{cust\_delivery}} - T_{\text{promise}}$$
$$\text{Penalty}_{\text{sla}} = \Delta t_{\text{sla}} \times C_{\text{sla\_rate\_per\_hr}}$$
The customer fulfillment node transitions to `BREACHED`.

#### 4. Total Financial Exposure
$$\text{Financial Risk (₹)} = \text{Penalty}_{\text{driver}} + \text{Penalty}_{\text{missed\_slot}} + \text{Cost}_{\text{overtime}} + \text{Penalty}_{\text{sla}}$$

### 4.3 Exposed Functional API
```python
compute_cascade_impact(shipment_id: str, added_delay_hours: float) -> CascadeImpact
```

---

## 5. Benchmark Fixture Simulation: 4-Hour Delay on `SHP-1005`

### 5.1 Input Parameters (`SHP-1005`)
- **Origin / Destination**: Nhava Sheva (JNPT) $\rightarrow$ Bhiwandi Logistics Hub
- **Cargo Value**: ₹45,00,000 (Electronics & Automotive Parts)
- **Port Berth Scheduled**: 08:00 AM
- **Truck Pickup Scheduled**: 09:00 AM (Max wait: 2.0 hrs, Waiting rate: ₹500/hr)
- **Highway Transit Time**: 3.5 hrs
- **Warehouse Slot Scheduled**: 01:30 PM (Buffer: 45 min, Cutoff: 02:15 PM, Missed fee: ₹12,500, Overtime: ₹1,800/hr)
- **Customer Promise Time**: 05:00 PM (SLA penalty: ₹3,000/hr)

### 5.2 Simulation Results Under +4.0 Hours Port Berth Delay
```
[1] Port Berth Arrival Node:
    Scheduled: 08:00 | Projected: 12:00 | Delay: +4.0 hrs -> DELAYED

[2] Truck Pickup Node:
    Scheduled: 09:00 | Projected: 12:00 | Driver Wait: 3.0 hrs (Limit: 2.0 hrs)
    Status: BREACHED -> Driver Detention Penalty: ₹1,500.00

[3] Warehouse Dock Delivery Node:
    Scheduled: 13:30 | Buffer Cutoff: 14:15 | Projected Arrival: 15:30
    Status: BREACHED -> Missed Slot Fee: ₹12,500.00
    Overtime: 1.25 hrs -> Overtime Labor Surcharge: ₹2,250.00

[4] Customer Fulfillment SLA Node:
    Scheduled: 17:00 | Projected Delivery: 17:30 | SLA Delay: 0.5 hrs
    Status: BREACHED -> Customer SLA Penalty: ₹1,500.00
```

- **Driver Waiting Penalty**: ₹1,500.00
- **Missed Slot Penalty**: ₹12,500.00
- **Warehouse Overtime Surcharge**: ₹2,250.00
- **Customer SLA Penalty**: ₹1,500.00
- **Total Financial Risk**: **₹17,750.00**
- **Composite Risk Level**: **`CRITICAL`**

---

## 6. Test Suite & Verification

The suite includes both module unit tests and comprehensive integration tests:

| Test File | Target | Result |
| :--- | :--- | :--- |
| `tests/test_risk_engine.py` | `RiskScorer`, `predict_risk`, 4h delay simulation | **Passed** |
| `tests/test_cascade.py` | `SupplyChainGraphBuilder`, `CascadeImpactAnalyzer`, `compute_cascade_impact`, zero-delay scenario | **Passed** |
| `tests/test_agents.py` | Agent negotiation round validation | **Passed** |
| `tests/test_database.py` | SQLite schema and CRUD persistence | **Passed** |
| `tests/test_simulation.py` | 50-run disruption generation benchmarks | **Passed** |
| `src/main.py` | End-to-end dry-run pipeline | **Passed** |

To execute all tests:
```bash
pytest tests/
```

To run standalone deliverable checks:
```bash
python3 risk_engine.py
python3 cascade_graph.py
```
