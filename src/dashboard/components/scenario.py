"""One scenario and one immutable pricing snapshot shared by dashboard views."""

import sqlite3

import streamlit as st

from src.agents.coordinator import CentralCoordinator
from src.cascade.impact_analyzer import build_cascade_graph, query_shipment_bundle, resolve_db_path

DISRUPTION_TYPES = ["PORT_CONGESTION", "VESSEL_DELAY", "TRUCK_BREAKDOWN", "TRAFFIC_INCIDENT", "WAREHOUSE_BOTTLENECK"]


def shipment_catalog():
    with sqlite3.connect(resolve_db_path()) as conn:
        rows = conn.execute("""SELECT s.shipment_id, s.origin_port, s.destination_hub
            FROM shipments s WHERE EXISTS (SELECT 1 FROM truck_bookings t WHERE t.shipment_id=s.shipment_id)
            AND EXISTS (SELECT 1 FROM warehouse_slots w WHERE w.shipment_id=s.shipment_id)
            ORDER BY CASE WHEN s.shipment_id='SHP-1005' THEN 0 ELSE 1 END, s.shipment_id""").fetchall()
    return {row[0]: f"{row[0]} · {row[1]} → {row[2]}" for row in rows}


def pricing_from_bundle(bundle):
    return {
        "driver_waiting_cost_per_hr": float(bundle["truck"]["driver_waiting_cost_per_hr"]),
        "sla_penalty_per_hour_inr": float(bundle["shipment"]["sla_penalty_per_hour_inr"]),
        "missed_slot_penalty_inr": float(bundle["warehouse"]["missed_slot_penalty_inr"]),
        "overtime_cost_per_hr": float(bundle["warehouse"]["overtime_cost_per_hr"]),
    }


def evaluate_scenario(shipment_id, disruption_type, delay_hours, bundle=None):
    bundle = bundle if bundle is not None else query_shipment_bundle(shipment_id)
    pricing = pricing_from_bundle(bundle)
    _, impact = build_cascade_graph(bundle, delay_hours, disruption_type)
    plans = CentralCoordinator().run_recovery_negotiation(impact, pricing=pricing)
    signature = (shipment_id, disruption_type, float(delay_hours), tuple(pricing.items()),
                 repr(bundle))
    return {"bundle": bundle, "pricing": pricing, "impact": impact, "plans": plans,
            "signature": signature, "disruption_type": disruption_type, "delay_hours": delay_hours}


def render_scenario_controls():
    catalog = shipment_catalog()
    if not catalog:
        st.error("No consignments with truck and warehouse bookings are available.")
        st.stop()
    if st.session_state.get("scenario_shipment") not in catalog:
        st.session_state["scenario_shipment"] = st.session_state.get("current_shipment_id", next(iter(catalog)))
    if "scenario_disruption" not in st.session_state:
        st.session_state["scenario_disruption"] = st.session_state.get("current_disruption_type", "PORT_CONGESTION")
    if "scenario_delay" not in st.session_state:
        st.session_state["scenario_delay"] = float(st.session_state.get("current_delay_hours", 4.0))
    st.caption("Shared scenario • Operations, Recovery & Approval, and Geographic Simulation use these same inputs and applied tariffs.")
    a, b, c = st.columns([2, 1.4, 1.5])
    with a:
        shipment_id = st.selectbox("Active ship / consignment", list(catalog), format_func=catalog.get, key="scenario_shipment")
    with b:
        disruption_type = st.selectbox("Disruption type", DISRUPTION_TYPES, format_func=lambda v: v.replace("_", " ").title(), key="scenario_disruption")
    with c:
        delay_hours = st.slider("Added delay (hours)", 0.0, 8.0, step=0.5, key="scenario_delay")
    # Re-read applied DB tariffs on every rerun; a CSV/reset cannot leave an old
    # impact paired with freshly negotiated plans.
    result = evaluate_scenario(shipment_id, disruption_type, delay_hours)
    if st.session_state.get("scenario_signature") != result["signature"]:
        for key in list(st.session_state):
            if key.startswith(("last_custom_", "explanation_")) or key in ("selected_plan", "plan_approved", "active_explanation"):
                del st.session_state[key]
        st.session_state["force_regenerate_explanation"] = True
    st.session_state.update({
        "scenario_signature": result["signature"], "current_scenario": result,
        "current_impact": result["impact"], "current_shipment_id": shipment_id,
        "current_delay_hours": delay_hours, "current_disruption_type": disruption_type,
        "negotiated_plans": result["plans"],
    })
