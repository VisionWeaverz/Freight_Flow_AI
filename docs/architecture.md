# FreightFlow AI - System Architecture & Module Boundaries

## 1. High-Level Architecture Overview

FreightFlow AI is an autonomous disruption prediction and multi-party recovery platform designed for modern logistics networks (Ports, Trucking Carriers, Distribution Centers/Warehouses).

```
+-----------------------------------------------------------------------------------+
|                            Streamlit Web Dashboard                                |
|  - Real-time Operations  - Cascade Impact View (₹ at risk)  - Plan Approval (LLM) |
+------------------------------------------^----------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
|                         FreightFlow Master Orchestrator                           |
|      (Manages pipeline lifecycle, event ingestion, and cross-module execution)     |
+-------------+----------------------------+-------------------------+--------------+
              |                            |                         |
              v                            v                         v
   [ 1. Risk Scorer ]            [ 2. Cascade Graph ]      [ 3. Multi-Agent System ]
  - scikit-learn model          - NetworkX dependency     - Central Coordinator
  - Synthetic training data       graph                   - Carrier Agent (cost, wait)
  - Early disruption flag       - Downstream nodes        - Port Agent (berth, gate)
                                - INR (₹) at risk calc    - Warehouse Agent (slots, OT)
                                                          - 2-3 negotiation rounds
                                                          - Top 3 Pareto recovery plans
                                                                     |
                                                                     v
                                                            [ 4. LLM Explainer ]
                                                          - Natural language summary
                                                          - Trade-off reasoning
                                                                     |
                                                                     v
                                                          [ 5. SQLite Storage ]
                                                          - Shipments, slots, logs
```

---

## 2. Decoupled Subsystems

To allow team members to build and test features in isolation, the system is separated into three distinct domains with standardized interfaces:

### Subsystem A: Machine Learning, Simulation & Cascade Impact
- **Location:** `src/risk_engine/`, `src/cascade/`, `src/simulation/`
- **Responsibilities:**
  - Synthetic dataset generation for port arrival delays, traffic congestion, and truck breakdowns.
  - Delay classification and regression model (`scikit-learn`).
  - Graph dependency topology (`NetworkX`) mapping port berths, carriers, and warehouse bays.
  - Recursive traversal to compute downstream delayed shipments and total monetary value (₹ at risk).
  - 50-run simulation benchmark runner comparing FreightFlow AI replanning against a First-Come, First-Served manual baseline.

### Subsystem B: Autonomous Multi-Agent Negotiation & AI Reasoning
- **Location:** `src/agents/`, `src/llm/`
- **Responsibilities:**
  - Specialized agents (`CarrierAgent`, `PortAgent`, `WarehouseAgent`), each encapsulating its private cost models and physical capacity constraints.
  - Scripted 2-to-3 round negotiation protocol managed by `CentralCoordinator` (Initial offer -> Counter offer -> Best and final offer).
  - Pareto ranking producing Top 3 plans:
    1. **Cheapest:** Minimizes financial surcharge and penalty costs.
    2. **Fastest:** Minimizes customer delay and transit downtime.
    3. **Safest:** Maximizes schedule reliability and operational slack buffer.
  - LLM integration (`LLMExplainer`) generating human-in-the-loop rationale and unstructured disruption event parsing.

### Subsystem C: Data Persistence & Streamlit Interactive UI
- **Location:** `src/database/`, `src/dashboard/`
- **Responsibilities:**
  - Relational schema and ORM models (`SQLite` + `SQLAlchemy`) for shipments, slot reservations, disruption logs, and recovery plans.
  - Database initialization and seed script with mock logistics itineraries.
  - Interactive multi-page Streamlit dashboard featuring:
    - Operational overview and live alerts.
    - Cascade graph visualization.
    - Side-by-side comparison of Top 3 recovery plans.
    - One-click human approval mechanism.
    - Before-and-after operational timeline/Gantt view.
    - Benchmark analytics charts across 50 simulated disruption trials.
