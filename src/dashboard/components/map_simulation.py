"""Geographic incident replay backed by the existing cascade and negotiation engines."""

import json
from datetime import datetime, timedelta
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from src.dashboard.components.scenario import evaluate_scenario, shipment_catalog

ASSETS = Path(__file__).with_name("simulation_assets")
DISRUPTIONS = {
    "Port congestion": "PORT_CONGESTION",
    "Vessel delay": "VESSEL_DELAY",
    "Truck breakdown": "TRUCK_BREAKDOWN",
    "Highway traffic": "TRAFFIC_INCIDENT",
    "Warehouse bottleneck": "WAREHOUSE_BOTTLENECK",
}


def build_replay_payload(bundle, disruption_type, delay_hours, rates=None, scenario=None):
    """Keep the disrupted replay exact; derive causal recovery previews from plan actions.

    RecoveryPlan contains aggregate delay, not milestone timestamps. The recovery
    preview therefore derives sequential times from the chosen slots and explicitly
    exposes that distinction instead of reusing the dashboard's illustrative times.
    """
    scenario = scenario or evaluate_scenario(bundle["shipment"]["shipment_id"], disruption_type, delay_hours, bundle=bundle)
    impact, plans, rates = scenario["impact"], scenario["plans"], scenario["pricing"]
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
    geography = geography_for(shp["origin_port"], shp["destination_hub"])
    route_path = ASSETS / geography["routeFile"]
    route = json.loads(route_path.read_text()) if route_path.is_file() else None
    return {
        "geography": geography,
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


def geography_for(origin, destination):
    ports = {"Nhava Sheva (JNPT)": [18.949, 72.951], "JNPT": [18.949, 72.951],
             "Chennai Port": [13.1, 80.30], "Mundra Port": [22.74, 69.70],
             "Pipavav Port": [20.915, 71.515], "Kolkata Port": [22.54, 88.30]}
    hubs = {"Bhiwandi Hub": [19.281, 73.048], "Bhiwandi": [19.281, 73.048],
            "Sriperumbudur Mega Hub": [12.967, 79.948], "Ahmedabad Ring Hub": [23.04, 72.57],
            "Bengaluru Whitefield Hub": [12.97, 77.75], "Gurugram Logistics Park": [28.45, 77.02]}
    port, hub = ports.get(origin), hubs.get(destination)
    if port is None or hub is None:
        raise ValueError(f"Map coordinates unavailable for {origin} → {destination}")
    is_jnpt = origin in ("Nhava Sheva (JNPT)", "JNPT")
    is_bhiwandi = destination in ("Bhiwandi Hub", "Bhiwandi")
    filename = "jnpt_bhiwandi_route.json" if is_jnpt and is_bhiwandi else f"route_{port[0]}_{port[1]}_{hub[0]}_{hub[1]}.json"
    # Approximate offshore positions; facilities are illustrative, not telemetry.
    anchor = [port[0] - .07, port[1] - .07] if origin not in ("Chennai Port", "Kolkata Port") else [port[0] - .02, port[1] + .08]
    return {"port": port, "warehouse": hub, "customer": [hub[0] + .023, hub[1] + .014],
            "anchor": anchor, "routeFile": filename}


def render_map_simulation():
    st.markdown("### Geographic incident replay")
    scenario = st.session_state["current_scenario"]
    bundle = scenario["bundle"]
    shipment_id = bundle["shipment"]["shipment_id"]
    disruption_type, delay = scenario["disruption_type"], scenario["delay_hours"]
    st.caption(f"Shared scenario: {shipment_id} · {disruption_type.replace('_', ' ').title()} · +{delay:.1f}h. Costs match Operations and Recovery & Approval. Vehicle positions are simulated.")
    catalog = shipment_catalog()
    comparison_ids = st.multiselect("Additional ships / consignments to compare", list(catalog),
        format_func=catalog.get, key="map_comparison_ships", max_selections=5,
        help="The active shipment is always displayed. Add up to five others. Each is evaluated independently with the same disruption and delay, using its own bookings and tariffs.")
    payload = build_replay_payload(bundle, disruption_type, delay, scenario=scenario)
    fleet = []
    rows = []
    for sid in [shipment_id] + [sid for sid in comparison_ids if sid != shipment_id]:
        result = scenario if sid == shipment_id else evaluate_scenario(sid, disruption_type, delay)
        replay = payload if sid == shipment_id else build_replay_payload(result["bundle"], disruption_type, delay, scenario=result)
        rows.append({"Shipment": sid, "Unmitigated exposure (₹)": result["impact"].financial_risk_inr,
                     **{p.category.value.title() + " operating fee (₹)": p.total_cost_inr for p in result["plans"]}})
        if sid != shipment_id:
            fleet.append({key: value for key, value in replay.items() if key != "fleet"})
    payload["fleet"] = fleet
    payload["end"] = max([payload["end"]] + [entry["end"] for entry in fleet])
    template = (ASSETS / "replay.html").read_text()
    serialized = json.dumps(payload).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    components.html(template.replace("__REPLAY_DATA__", serialized), height=900, scrolling=False)
    st.dataframe(rows, hide_index=True, use_container_width=True)
    st.caption("Every price above is calculated once from the shared scenario and applied tariffs. Recovery prices are operating fees, excluding residual SLA penalties. Additional shipments are independent comparisons aligned by elapsed replay time, not a joint fleet optimization. Facility markers and vessel approach are illustrative; routes without stored road geometry are dashed. Basemaps require internet.")
