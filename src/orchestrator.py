"""End-to-End Orchestrator connecting Prediction, Cascade Analysis, Negotiation, and UI/DB."""

from typing import Dict, Any, Tuple, List
from src.common.schemas import DisruptionEvent, RecoveryPlan, CascadeImpact
from src.risk_engine.scorer import RiskScorer
from src.cascade.impact_analyzer import CascadeImpactAnalyzer
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
        1. Predict risk level & severity.
        2. Build cascade graph & calculate downstream INR at risk.
        3. Trigger multi-agent negotiation rounds.
        4. Synthesize Top 3 plans (Cheapest, Fastest, Safest).
        5. Explain top plan with LLM.
        """
        # 1. Prediction
        risk_prediction = self.risk_scorer.predict_risk({"shipment_id": disruption.source_entity_id})

        # 2. Cascade Mapping
        graph = self.graph_builder.build_graph([])
        analyzer = CascadeImpactAnalyzer(graph)
        cascade_impact = analyzer.compute_impact(disruption)

        # 3. Autonomous Negotiation
        plans, is_feasible = self.coordinator.coordinate_recovery(disruption)

        # 4. LLM Explanations
        if plans and is_feasible:
            for plan in plans:
                plan.llm_explanation = self.llm_explainer.explain_plan(disruption, plan)

        return {
            "disruption": disruption,
            "risk_prediction": risk_prediction,
            "cascade_impact": cascade_impact,
            "plans": plans,
            "is_feasible": is_feasible
        }
