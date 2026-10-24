"""Unit tests for Rate Manager and CSV Tariff Ingestion."""

import pytest
import sqlite3
import tempfile
import os
from src.database.rate_manager import (
    parse_pricing_csv,
    apply_pricing_to_db,
    reset_pricing_to_synthetic,
    get_active_pricing,
    get_sample_csv_template,
    SYNTHETIC_BASELINE_RATES
)
from src.cascade.impact_analyzer import compute_cascade_impact


def test_parse_pricing_csv_key_value():
    csv_text = """rate_name,rate_inr,unit
driver_waiting_cost_per_hr,800.0,per_hour
sla_penalty_per_hour_inr,4500.0,per_hour
missed_slot_penalty_inr,16000.0,flat
overtime_cost_per_hr,2200.0,per_hour
"""
    success, msg, rates = parse_pricing_csv(csv_text)
    assert success is True
    assert rates["driver_waiting_cost_per_hr"] == 800.0
    assert rates["sla_penalty_per_hour_inr"] == 4500.0
    assert rates["missed_slot_penalty_inr"] == 16000.0
    assert rates["overtime_cost_per_hr"] == 2200.0


def test_parse_pricing_csv_columnar():
    csv_text = """shipment_id,driver_waiting_cost_per_hr,sla_penalty_per_hour_inr,missed_slot_penalty_inr,overtime_cost_per_hr
SHP-1005,950,5500,20000,2800
"""
    success, msg, rates = parse_pricing_csv(csv_text)
    assert success is True
    assert rates["driver_waiting_cost_per_hr"] == 950.0
    assert rates["sla_penalty_per_hour_inr"] == 5500.0
    assert rates["missed_slot_penalty_inr"] == 20000.0
    assert rates["overtime_cost_per_hr"] == 2800.0


def test_parse_pricing_csv_aliases():
    csv_text = """metric,value
driver_detention_rate,650
customer_sla_fine,3800
dock_missed_penalty,14000
warehouse_overtime_rate,2100
"""
    success, msg, rates = parse_pricing_csv(csv_text)
    assert success is True
    assert rates["driver_waiting_cost_per_hr"] == 650.0
    assert rates["sla_penalty_per_hour_inr"] == 3800.0
    assert rates["missed_slot_penalty_inr"] == 14000.0
    assert rates["overtime_cost_per_hr"] == 2100.0


def test_parse_pricing_csv_invalid_negative():
    csv_text = """rate_name,rate_inr
driver_waiting_cost_per_hr,-500
"""
    success, msg, rates = parse_pricing_csv(csv_text)
    assert success is False
    assert "cannot be negative" in msg


def test_parse_pricing_csv_empty():
    success, msg, rates = parse_pricing_csv("")
    assert success is False
    assert "empty" in msg.lower()


def test_apply_and_reset_pricing():
    # Test applying rates to active database
    test_rates = {
        "driver_waiting_cost_per_hr": 777.0,
        "sla_penalty_per_hour_inr": 3777.0,
        "missed_slot_penalty_inr": 13777.0,
        "overtime_cost_per_hr": 1977.0,
    }
    success, msg = apply_pricing_to_db(test_rates, apply_to_all=True)
    assert success is True

    active = get_active_pricing("SHP-1005")
    assert active["driver_waiting_cost_per_hr"] == 777.0
    assert active["sla_penalty_per_hour_inr"] == 3777.0
    assert active["missed_slot_penalty_inr"] == 13777.0
    assert active["overtime_cost_per_hr"] == 1977.0

    # Reset back to synthetic baseline
    reset_success, reset_msg = reset_pricing_to_synthetic(reset_all=True)
    assert reset_success is True

    restored = get_active_pricing("SHP-1005")
    assert restored["driver_waiting_cost_per_hr"] == SYNTHETIC_BASELINE_RATES["driver_waiting_cost_per_hr"]
    assert restored["sla_penalty_per_hour_inr"] == SYNTHETIC_BASELINE_RATES["sla_penalty_per_hour_inr"]
    assert restored["missed_slot_penalty_inr"] == SYNTHETIC_BASELINE_RATES["missed_slot_penalty_inr"]
    assert restored["overtime_cost_per_hr"] == SYNTHETIC_BASELINE_RATES["overtime_cost_per_hr"]


def test_cascade_financial_impact_with_custom_pricing():
    # Reset baseline first
    reset_pricing_to_synthetic(reset_all=True)
    baseline_impact = compute_cascade_impact("SHP-1005", added_delay_hours=4.0, disruption_type="PORT_CONGESTION")
    baseline_cost = baseline_impact.financial_risk_inr

    # Double the rates
    higher_rates = {
        "driver_waiting_cost_per_hr": 1000.0,  # was 500
        "sla_penalty_per_hour_inr": 6000.0,    # was 3000
        "missed_slot_penalty_inr": 25000.0,    # was 12500
        "overtime_cost_per_hr": 3600.0,        # was 1800
    }
    apply_pricing_to_db(higher_rates, apply_to_all=True)

    higher_impact = compute_cascade_impact("SHP-1005", added_delay_hours=4.0, disruption_type="PORT_CONGESTION")
    higher_cost = higher_impact.financial_risk_inr

    assert higher_cost > baseline_cost, f"Higher rates should increase financial risk: {higher_cost} vs {baseline_cost}"
    assert higher_cost == pytest.approx(baseline_cost * 2, rel=0.05)

    # Clean up: restore baseline
    reset_pricing_to_synthetic(reset_all=True)


def test_template_generation():
    kv_template = get_sample_csv_template("key_value")
    assert "driver_waiting_cost_per_hr" in kv_template
    assert "sla_penalty_per_hour_inr" in kv_template

    col_template = get_sample_csv_template("columnar")
    assert "shipment_id,driver_waiting_cost_per_hr" in col_template
