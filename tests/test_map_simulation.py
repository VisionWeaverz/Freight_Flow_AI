"""Geographic replay contracts without touching the running app's database."""

import pytest

from src.dashboard.components.map_simulation import build_replay_payload, DISRUPTIONS
from src.database import rate_manager


@pytest.fixture(autouse=True)
def ensure_freightflow_db(monkeypatch):
    """Override the suite's destructive database seeder for these pure tests."""
    monkeypatch.setattr(rate_manager, "get_active_pricing", lambda shipment_id: dict(rate_manager.SYNTHETIC_BASELINE_RATES))


@pytest.fixture
def bundle():
    return {
        "shipment": {
            "shipment_id": "SHP-1005", "origin_port": "JNPT", "destination_hub": "Bhiwandi",
            "eta_port_berth": "2026-10-23T08:00:00", "customer_promise_time": "2026-10-23T17:00:00",
            "customer_name": "Test customer", "sla_penalty_per_hour_inr": 3000,
        },
        "truck": {
            "booking_id": "TRK-1005", "driver_name": "Test driver", "truck_number": "MH-04-AB-1005",
            "scheduled_pickup_time": "2026-10-23T09:00:00", "max_driver_wait_hours_allowed": 2,
            "driver_waiting_cost_per_hr": 500, "transit_time_hours": 3.5,
        },
        "warehouse": {
            "slot_id": "SLOT-1005", "warehouse_id": "WHS-BHIWANDI-A", "dock_bay": "BAY-7",
            "scheduled_slot_time": "2026-10-23T13:30:00", "max_buffer_minutes": 45,
            "missed_slot_penalty_inr": 12500, "overtime_cost_per_hr": 1800,
        },
    }


@pytest.mark.parametrize("disruption", DISRUPTIONS.values())
@pytest.mark.parametrize("delay", [0, 4, 8])
def test_replay_schedules_are_causal(bundle, disruption, delay):
    p = build_replay_payload(bundle, disruption, delay, rate_manager.SYNTHETIC_BASELINE_RATES)
    assert p["disrupted"]["berth"] <= p["disrupted"]["pickup"] <= p["disrupted"]["arrival"] <= p["disrupted"]["delivery"]
    assert p["risk"] == sum(p["penalties"].values())
    for plan in p["plans"]:
        s = plan["schedule"]
        assert s["berth"] <= s["pickup"] <= s["arrival"] <= s["intake"] < s["delivery"] < p["end"]
        assert plan["cost"] == sum(plan["breakdown"].values())
        if "MORNING" in plan["slots"][2]:
            assert (p["startHour"] + s["intake"]) % 24 == 8


def test_flagship_replay_matches_existing_cascade(bundle):
    p = build_replay_payload(bundle, "PORT_CONGESTION", 4, rate_manager.SYNTHETIC_BASELINE_RATES)
    assert p["risk"] == 17750
    assert p["disrupted"] == {"berth": 6, "pickup": 6, "arrival": 9.5, "delivery": 11.5}
    assert p["route"]["distanceKm"] > 0
    assert len(p["route"]["coordinates"]) > 100


def test_applied_tariffs_reach_map_and_recovery(bundle, monkeypatch):
    rates = dict(rate_manager.SYNTHETIC_BASELINE_RATES, driver_waiting_cost_per_hr=900, overtime_cost_per_hr=2400)
    bundle["truck"]["driver_waiting_cost_per_hr"] = 900
    bundle["warehouse"]["overtime_cost_per_hr"] = 2400
    monkeypatch.setattr(rate_manager, "get_active_pricing", lambda shipment_id: rates)
    p = build_replay_payload(bundle, "PORT_CONGESTION", 4, rates)
    assert p["risk"] == 19700
    assert p["rates"] == rates
    cheapest = next(plan for plan in p["plans"] if plan["category"] == "CHEAPEST")
    assert cheapest["breakdown"]["carrier"] == 2700
