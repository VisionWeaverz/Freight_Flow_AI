"""Recovery pricing regressions using an isolated database."""

import sqlite3

import pytest

from src.agents.coordinator import CentralCoordinator
from src.common.schemas import CascadeImpact, PlanCategory
from src.database import rate_manager


@pytest.fixture(autouse=True)
def ensure_freightflow_db(tmp_path, monkeypatch):
    # Override the suite's live-database seeder for these isolated tests.
    db = tmp_path / "pricing.db"
    with sqlite3.connect(db) as conn:
        conn.executescript("""
            CREATE TABLE shipments (shipment_id TEXT, sla_penalty_per_hour_inr REAL);
            CREATE TABLE truck_bookings (shipment_id TEXT, driver_waiting_cost_per_hr REAL);
            CREATE TABLE warehouse_slots (
                shipment_id TEXT, missed_slot_penalty_inr REAL, overtime_cost_per_hr REAL
            );
            INSERT INTO shipments VALUES ('SHP-1005', 3000);
            INSERT INTO truck_bookings VALUES ('SHP-1005', 500);
            INSERT INTO warehouse_slots VALUES ('SHP-1005', 12500, 1800);
        """)
    monkeypatch.setattr(rate_manager, "DEFAULT_DB_CANDIDATES", [str(db)])


def test_csv_rates_affect_recovery_only_after_apply_and_reset():
    impact = CascadeImpact(
        shipment_id="SHP-1005", initial_delay_hours=2, risk_level="HIGH"
    )
    coordinator = CentralCoordinator()
    baseline = coordinator.run_recovery_negotiation(impact)
    ok, _, rates = rate_manager.parse_pricing_csv(
        "rate_name,rate_inr\ndriver_waiting_cost_per_hr,900\novertime_cost_per_hr,2400"
    )
    assert ok
    # Parsing alone must not activate the upload.
    unapplied = coordinator.run_recovery_negotiation(impact)
    assert [p.cost_breakdown for p in unapplied] == [p.cost_breakdown for p in baseline]

    assert rate_manager.apply_pricing_to_db(rates)[0]
    applied = coordinator.run_recovery_negotiation(impact)
    cheap = next(p for p in applied if p.category == PlanCategory.CHEAPEST)
    fast = next(p for p in applied if p.category == PlanCategory.FASTEST)
    assert cheap.cost_breakdown["carrier"] == 2 * 900
    assert fast.cost_breakdown["warehouse"] == 2 * 2400
    assert [p.total_cost_inr for p in applied] != [p.total_cost_inr for p in baseline]

    assert rate_manager.reset_pricing_to_synthetic()[0]
    restored = coordinator.run_recovery_negotiation(impact)
    assert [p.cost_breakdown for p in restored] == [p.cost_breakdown for p in baseline]


def test_carrier_supplemental_wait_option_uses_applied_rate():
    # At low risk, all three rounds choose replacement; WAIT is supplied by
    # get_alternatives, which previously used its default 500/hour.
    assert rate_manager.apply_pricing_to_db({"driver_waiting_cost_per_hr": 4000})[0]
    coordinator = CentralCoordinator()
    coordinator.run_recovery_negotiation(CascadeImpact(
        shipment_id="SHP-1005", initial_delay_hours=1.5, risk_level="LOW"
    ))
    options = coordinator._collect_distinct_options([], "CARRIER", 1.5)
    wait = next(option for option in options if option["type"] == "WAIT")
    assert wait["cost"] == 6000
