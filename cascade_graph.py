"""Root-level entrypoint and compatibility wrapper for NetworkX Cascade Disruption Engine."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.cascade.impact_analyzer import (
    compute_cascade_impact,
    build_cascade_graph,
    query_shipment_bundle,
    CascadeImpactAnalyzer
)
from src.cascade.graph_builder import SupplyChainGraphBuilder
from src.common.schemas import CascadeImpact, CascadeNode, CascadeEdge

if __name__ == "__main__":
    print("=" * 70)
    print("  FREIGHTFLOW AI - CASCADE GRAPH DELIVERABLE 2 TEST")
    print("=" * 70)

    test_shipment = "SHP-1005"
    test_delay = 4.0

    print(f"\nSimulating {test_delay}-hour port berth delay on '{test_shipment}'...")
    impact = compute_cascade_impact(test_shipment, test_delay)

    print("\n[Cascade Results]")
    print(f"Initial Port Delay    : +{impact.initial_delay_hours} hrs")
    print(f"Total Cascaded Delay  : +{impact.total_cascaded_delay_hours} hrs")
    print(f"Total Financial Risk  : ₹{impact.financial_risk_inr:,.2f}")
    print(f"Risk Level            : {impact.risk_level}")
    print(f"Affected Nodes ({len(impact.nodes)}) : {[n.name for n in impact.nodes]}")
    print("\nPenalty Breakdown:")
    for k, v in impact.penalty_breakdown.items():
        print(f"  - {k:<28}: ₹{v:,.2f}")

    assert isinstance(impact, CascadeImpact), "Must return CascadeImpact"
    assert len(impact.nodes) == 4, "Must contain 4 lifecycle nodes"
    assert impact.financial_risk_inr > 0, "Financial risk should be positive"
    assert impact.risk_level in ["HIGH", "CRITICAL"], "4-hour delay should be HIGH or CRITICAL"

    print("\n✅ Deliverable 2 Standalone Unit Test Passed!")
    print("=" * 70)
