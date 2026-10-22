"""Tests for risk scorer and feature extraction pipeline."""

from src.risk_engine.scorer import RiskScorer, predict_risk


def test_risk_scorer_prediction():
    scorer = RiskScorer()
    prediction = scorer.predict_risk({"shipment_id": "TEST-101"})
    assert prediction.shipment_id == "TEST-101"
    assert 0.0 <= prediction.risk_score <= 1.0


def test_predict_risk_shp_1005_four_hour_delay():
    """Unit test simulating 4-hour delay on SHP-1005."""
    score, level = predict_risk("SHP-1005", new_delay_hours=4.0, congestion=0.75)
    assert isinstance(score, float)
    assert 0.0 <= score <= 1.0
    assert level in ["HIGH", "CRITICAL"]


def test_predict_risk_nominal_conditions():
    """Unit test for on-time / low disruption conditions."""
    score, level = predict_risk("SHP-1005", new_delay_hours=0.0, congestion=0.20)
    assert 0.0 <= score <= 1.0
    assert level in ["LOW", "MEDIUM"]
