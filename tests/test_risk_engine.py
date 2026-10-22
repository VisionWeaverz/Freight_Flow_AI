"""Tests for risk scorer and feature extraction pipeline."""

from src.risk_engine.scorer import RiskScorer


def test_risk_scorer_prediction():
    scorer = RiskScorer()
    prediction = scorer.predict_risk({"shipment_id": "TEST-101"})
    assert prediction.shipment_id == "TEST-101"
    assert 0.0 <= prediction.risk_score <= 1.0
