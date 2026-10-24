"""Geographic incident replay backed by the existing cascade and negotiation engines."""

import json
from datetime import datetime, timedelta
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from src.agents.coordinator import CentralCoordinator
from src.cascade.impact_analyzer import build_cascade_graph, query_shipment_bundle
from src.database.rate_manager import get_active_pricing

ASSETS = Path(__file__).with_name("simulation_assets")
DISRUPTIONS = {
    "Port congestion": "PORT_CONGESTION",
    "Vessel delay": "VESSEL_DELAY",
    "Truck breakdown": "TRUCK_BREAKDOWN",
    "Highway traffic": "TRAFFIC_INCIDENT",
    "Warehouse bottleneck": "WAREHOUSE_BOTTLENECK",
}


def build_replay_payload(bundle, disruption_type, delay_hours, rates):
    """Keep the disrupted replay exact; derive causal recovery previews from plan actions.

    RecoveryPlan contains aggregate delay, not milestone timestamps. The recovery
    preview therefore derives sequential times from the chosen slots and explicitly
    exposes that distinction instead of reusing the dashboard's illustrative times.
    """
    _, impact = build_cascade_graph(bundle, delay_hours, disruption_type)
    plans = CentralCoordinator().run_recovery_negotiation(impact)
    shp, truck, whs = bundle["shipment"], bundle["truck"], bundle["warehouse"]
    berth = datetime.fromisoformat(shp["eta_port_berth"])
    origin = berth - timedelta(hours=2)
    pickup = datetime.fromisoformat(truck["scheduled_pickup_time"])
    slot = datetime.fromisoformat(whs["scheduled_slot_time"])
    promise = datetime.fromisoformat(shp["customer_promise_time"])

    def hour(value):
        return round((value - origin).total_seconds() / 3600, 4)

    by_type = {n.node_type: n for n in impact.nodes}
    disrupted = {
        "berth": hour(datetime.fromisoformat(by_type["PORT"].actual_or_projected_time)),
        "pickup": hour(datetime.fromisoformat(by_type["TRUCK"].actual_or_projected_time)),
        "arrival": hour(datetime.fromisoformat(by_type["WAREHOUSE"].actual_or_projected_time)),
        "delivery": hour(datetime.fromisoformat(by_type["CUSTOMER"].actual_or_projected_time)),
    }
    recovered = []
    for plan in plans:
        port_time = berth if "EXPEDITED" in plan.port_slot_id else datetime.fromisoformat(by_type["PORT"].actual_or_projected_time)
        depart = max(pickup, port_time)
        road_delay = delay_hours if disruption_type in ("TRUCK_BREAKDOWN", "TRAFFIC_INCIDENT") and "REPLACEMENT" not in plan.carrier_slot_id else 0
        arrival = depart + timedelta(hours=float(truck["transit_time_hours"]) + road_delay)
        intake = arrival
        morning = "MORNING" in plan.warehouse_slot_id
        if morning:
            intake = max(arrival, slot).replace(hour=8, minute=0, second=0, microsecond=0)
            if intake < max(arrival, slot):
                intake += timedelta(days=1)
        delivery = intake + timedelta(hours=1)
        recovered.append({
            "category": plan.category.value,
            "cost": plan.total_cost_inr,
            "reliability": plan.reliability_score,
            "coordinatorDelay": plan.total_delay_hours,
            "breakdown": plan.cost_breakdown,
            "slots": [plan.port_slot_id, plan.carrier_slot_id, plan.warehouse_slot_id],
            "schedule": {"berth": hour(port_time), "pickup": hour(depart), "arrival": hour(arrival), "intake": hour(intake), "delivery": hour(delivery)},
            "actions": [
                "Priority berth handling" if "EXPEDITED" in plan.port_slot_id else "Retain standard berth allocation",
                "Dispatch replacement truck" if "REPLACEMENT" in plan.carrier_slot_id else "Synchronize existing driver pickup",
                "Reserve next-morning intake" if morning else "Book evening overtime crew",
            ],
        })
    baseline_arrival = pickup + timedelta(hours=float(truck["transit_time_hours"]))
    end = max(disrupted["delivery"], *(p["schedule"]["delivery"] for p in recovered), hour(promise)) + 1
    route_path = ASSETS / "jnpt_bhiwandi_route.json"
    route = json.loads(route_path.read_text()) if route_path.exists() else None
    return {
        "shipment": shp["shipment_id"], "customer": shp["customer_name"],
        "truck": truck["truck_number"], "driver": truck["driver_name"], "bay": whs["dock_bay"],
        "originLabel": shp["origin_port"], "destinationLabel": shp["destination_hub"],
        "date": origin.strftime("%d %b %Y"), "startHour": origin.hour,
        "disruption": disruption_type, "delay": delay_hours,
        "rates": rates, "risk": impact.financial_risk_inr,
        "driverWait": float(by_type["TRUCK"].details["driver_wait_hours"]),
        "driverLimit": float(truck["max_driver_wait_hours_allowed"]),
        "slotBuffer": float(whs["max_buffer_minutes"]) / 60,
        "penalties": {k: v for k, v in impact.penalty_breakdown.items() if k != "total_financial_risk_inr"},
        "baseline": {"berth": hour(berth), "pickup": hour(pickup), "arrival": hour(baseline_arrival), "delivery": hour(baseline_arrival + timedelta(hours=1))},
        "disrupted": disrupted, "plans": recovered,
        "slot": hour(slot), "cutoff": hour(slot + timedelta(minutes=float(whs["max_buffer_minutes"]))),
        "promise": hour(promise), "end": end,
        "route": route,
    }


def render_map_simulation():
    st.markdown("### Geographic incident replay")
    st.caption("JNPT → Bhiwandi • SHP-1005 • Real geography, simulated vehicle telemetry. Uses your active database tariffs.")
    a, b, c = st.columns([1.5, 2, 1.2])
    with a:
        disruption = st.selectbox("Simulation disruption", list(DISRUPTIONS), key="map_disruption")
    with b:
        delay = st.slider("Added delay (hours)", 0.0, 8.0, 4.0, 0.5, key="map_delay")
    with c:
        rates = get_active_pricing("SHP-1005")
        st.metric("Applied driver tariff", f"₹{rates['driver_waiting_cost_per_hr']:,.0f}/h")
    try:
        payload = build_replay_payload(query_shipment_bundle("SHP-1005"), DISRUPTIONS[disruption], delay, rates)
    except (ValueError, OSError) as exc:
        st.error(f"Cannot load the simulation shipment: {exc}")
        return
    template = (ASSETS / "replay.html").read_text()
    # Keep database strings inert inside the script element.
    serialized = json.dumps(payload).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    components.html(template.replace("__REPLAY_DATA__", serialized), height=900, scrolling=False)
    st.caption("Recovery is a preview, not an operational approval. Animated recovery times are derived from slot actions and transit duration; the coordinator’s aggregate delay estimate is shown separately. Facility markers are illustrative locations within the corridor. Basemaps need internet access.")
