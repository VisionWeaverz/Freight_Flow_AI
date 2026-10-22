"""FreightFlow AI - CLI Entry Point and Simulation Demonstration."""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.common.schemas import DisruptionEvent, DisruptionType
from src.orchestrator import FreightFlowOrchestrator


def run_demo():
    print("=" * 65)
    print("🚢 FreightFlow AI: Disruption Prediction & Recovery")
    print("=" * 65)

    orchestrator = FreightFlowOrchestrator()

    # Create a sample simulated disruption
    sample_disruption = DisruptionEvent(
        event_id="EVT-JNPT-001",
        event_type=DisruptionType.PORT_CONGESTION,
        source_entity_id="PORT_JNPT_BERTH_2",
        severity_level=0.75,
        delay_hours=4.0,
        description="Cargo ready 2:00 PM instead of scheduled 10:00 AM (JNPT Berth Congestion)"
    )

    print(f"\n[1] Disruption Detected: {sample_disruption.description}")
    print(f"    Delay: +{sample_disruption.delay_hours} hrs | Severity: {sample_disruption.severity_level * 100:.0f}%")

    # Run the orchestrator pipeline
    result = orchestrator.handle_disruption_pipeline(sample_disruption)

    print("\n[2] Risk Prediction:")
    pred = result["risk_prediction"]
    print(f"    High Risk: {pred.is_high_risk} (Score: {pred.risk_score:.2f})")
    print(f"    Key Factors: {', '.join(pred.key_factors)}")

    print("\n[3] Autonomous Multi-Agent Negotiation Results:")
    for plan in result["plans"]:
        print(f"    • [{plan.category.value}] Total Cost: ₹{plan.total_cost_inr:,.2f} | Delay: +{plan.total_delay_hours} hrs | Reliability: {plan.reliability_score * 100:.0f}%")
        if plan.llm_explanation:
            print(f"      AI Reasoning: {plan.llm_explanation}")

    print("\n" + "=" * 65)
    print("FreightFlow AI ready. Launch web UI with: streamlit run src/dashboard/app.py")
    print("=" * 65)


if __name__ == "__main__":
    run_demo()
