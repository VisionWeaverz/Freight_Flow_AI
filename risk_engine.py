"""Root-level entrypoint and compatibility wrapper for Risk Classifier Engine."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.risk_engine.scorer import predict_risk, RiskScorer, map_score_to_level
from src.risk_engine.train import train_risk_model
from src.risk_engine.feature_pipeline import FeaturePipeline

if __name__ == "__main__":
    print("=" * 65)
    print("  FREIGHTFLOW AI - RISK CLASSIFIER DELIVERABLE 1 TEST")
    print("=" * 65)

    test_shipment = "SHP-1005"
    test_delay = 4.0
    test_congestion = 0.75

    print(f"\nSimulating {test_delay}h delay with {test_congestion} congestion on '{test_shipment}'...")
    score, level = predict_risk(test_shipment, test_delay, test_congestion)

    print(f"Risk Score : {score:.4f} (range 0.0 - 1.0)")
    print(f"Risk Level : {level}")

    assert 0.0 <= score <= 1.0, "Risk score must be between 0.0 and 1.0"
    assert level in ["LOW", "MEDIUM", "HIGH", "CRITICAL"], "Invalid risk level tier"
    print("\n✅ Deliverable 1 Standalone Unit Test Passed!")
    print("=" * 65)
