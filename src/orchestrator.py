"""End-to-End Orchestrator connecting Prediction, Cascade Analysis, Negotiation, and UI/DB."""

from typing import Dict, Any
from src.common.schemas import DisruptionEvent, CascadeImpact
from src.risk_engine.scorer import RiskScorer
from src.cascade.impact_analyzer import (
    CascadeImpactAnalyzer,
    compute_cascade_impact,
)
from src.cascade.graph_builder import SupplyChainGraphBuilder
from src.agents.coordinator import CentralCoordinator
from src.llm.explainer import LLMExplainer


class FreightFlowOrchestrator:
    """Master pipeline managing prediction, cascade modeling, and agent negotiation."""

    def __init__(self):
        self.risk_scorer = RiskScorer()
        self.graph_builder = SupplyChainGraphBuilder()
        self.coordinator = CentralCoordinator()
        self.llm_explainer = LLMExplainer()

    def handle_disruption_pipeline(self, disruption: DisruptionEvent) -> Dict[str, Any]:
        """Runs the complete FreightFlow AI lifecycle:
        1. Predict risk level & severity — using actual delay_hours and congestion.
        2. Build cascade graph & calculate downstream INR at risk (computed once).
           - SHP-* IDs: uses compute_cascade_impact() for real DB-backed penalty math.
           - Other IDs: uses generic BFS approximation for entity disruptions.
        3. Trigger multi-agent negotiation rounds with actual CascadeImpact.
        4. Synthesize Top 3 plans (Cheapest, Fastest, Safest) verified by Pareto dominance.
        5. Explain top plan with LLM explainer.
        """
        if disruption.delay_hours < 0:
            raise ValueError(
                f"FreightFlowOrchestrator: disruption.delay_hours must be >= 0, got {disruption.delay_hours}"
            )

        # 1. Risk Prediction — pass real disruption features, not just the ID
        risk_prediction = self.risk_scorer.predict_risk({
            "shipment_id": disruption.source_entity_id,
            "delay_hours": disruption.delay_hours,
            "port_congestion_index": disruption.severity_level,
        })

        # 2. Cascade Mapping (computed exactly once to avoid redundant work)
        cascade_impact = self._compute_cascade(disruption)

        # 3. Autonomous Negotiation — pass actual CascadeImpact to coordinator
        plans = self.coordinator.run_recovery_negotiation(cascade_impact)
        is_feasible = any(p.is_feasible for p in plans) if plans else False

        # 4. LLM Explanations
        if plans and is_feasible:
            for plan in plans:
                plan.llm_explanation = self.llm_explainer.explain_plan(disruption, plan)

        return {
            "disruption": disruption,
            "risk_prediction": risk_prediction,
            "cascade_impact": cascade_impact,
            "plans": plans,
            "is_feasible": is_feasible,
        }

    def _compute_cascade(self, disruption: DisruptionEvent) -> CascadeImpact:
        """Routes cascade computation based on disruption source type.

        SHP-* entity IDs are real tracked shipments: uses compute_cascade_impact()
        with exact DB-backed 4-node penalty math. If the shipment is missing or
        invalid, raises ValueError explicitly rather than fabricating an arbitrary plan.

        Non-shipment entity IDs (e.g. PORT_JNPT_BERTH_2, TRUCK-FLEET-T1) use the
        generic BFS fallback appropriate for facility-level disruptions.
        """
        entity_id = disruption.source_entity_id

        if entity_id.startswith("SHP-"):
            # Real shipment ID: compute_cascade_impact must validate against DB.
            # Missing or invalid shipment IDs raise ValueError explicitly.
            impact = compute_cascade_impact(entity_id, disruption.delay_hours)
            impact.disruption_event_id = disruption.event_id
            return impact

        # Generic BFS fallback for non-shipment entity IDs
        graph = self.graph_builder.build_graph([])
        analyzer = CascadeImpactAnalyzer(graph)
        return analyzer.compute_impact(disruption)
