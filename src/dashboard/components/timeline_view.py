"""Before vs After schedule comparison view."""

import streamlit as st
from datetime import datetime, timedelta
from src.common.schemas import PlanCategory


def render_timeline_view():
    """Renders before and after schedule comparison table/timeline."""
    st.markdown("### 4. Schedule Realignment: Before vs. Disrupted vs. Recovered")
    st.caption("Visualizes dynamic milestone recovery to eliminate cascading supply chain failure.")

    plan = st.session_state.get("selected_plan")
    impact = st.session_state.get("current_impact")
    delay_hours = st.session_state.get("current_delay_hours", 4.0)
    disruption_type = st.session_state.get("current_disruption_type", "PORT_CONGESTION")

    if not plan:
        st.info("Select a recovery plan above to view the realigned operational schedule.")
        return

    carrier_slot = getattr(plan, "carrier_slot_id", "TRUCK-WAIT-R1")
    port_slot = getattr(plan, "port_slot_id", "BERTH-SLOT-01")
    whs_slot = getattr(plan, "warehouse_slot_id", "DOCK-SLOT-01")
    cat = plan.category
    financial_risk = getattr(impact, "financial_risk_inr", 17750.0) if impact else 17750.0
    cost_saved = max(0.0, financial_risk - plan.total_cost_inr)

    # Dynamic Disrupted Cascade descriptions based on disruption type
    if disruption_type in ("TRUCK_BREAKDOWN", "TRAFFIC_INCIDENT"):
        incident_name = "Expressway Traffic Jam" if disruption_type == "TRAFFIC_INCIDENT" else "Highway Mechanical Breakdown"
        port_disrupted = "08:00 AM - 10:00 AM (ON TIME - Cleared on Schedule)"
        truck_disrupted = f"10:00 AM Pickup ➔ Stranded on Highway (+{delay_hours:.1f}h {incident_name} - BREACHED)"
        whs_disrupted = f"Missed 01:30 PM Grace Window by +{delay_hours:.1f}h (Dock Slot Forfeited - BREACHED)"
        cust_disrupted = f"Delayed by +{delay_hours:.1f}h past 05:00 PM (Late SLA Penalties Accruing - BREACHED)"
    elif disruption_type == "WAREHOUSE_BOTTLENECK":
        port_disrupted = "08:00 AM - 10:00 AM (ON TIME - Cleared on Schedule)"
        truck_disrupted = "10:00 AM - 01:30 PM (ON TIME - Arrived at Warehouse Gate)"
        whs_disrupted = f"Dock Intake Stalled by +{delay_hours:.1f}h (+{delay_hours:.1f}h Overtime Wage Surcharge - BREACHED)"
        cust_disrupted = f"Delayed by +{delay_hours:.1f}h (Contract Delivery Window Breached)"
    else:  # PORT_CONGESTION or VESSEL_DELAY
        port_disrupted = f"08:00 AM + {delay_hours:.1f}h ➔ Cleared 12:00 PM (+{delay_hours:.1f}h Berth Congestion)"
        truck_disrupted = f"Driver Arrived 10:00 AM, Idled until 12:00 PM (Driver Idle {delay_hours:.1f}h - BREACHED)"
        whs_disrupted = f"Arrived 03:30 PM, Missed 01:30 PM Grace Window (Dock Slot Forfeited - BREACHED)"
        cust_disrupted = f"Projected Arrival 07:00 PM (+{delay_hours:.1f}h Past SLA - ₹ Penalties Compounding)"

    # Dynamic Recovered milestone descriptions based on plan category & disruption origin
    is_road_disruption = disruption_type in ("TRUCK_BREAKDOWN", "TRAFFIC_INCIDENT")
    is_whs_disruption = disruption_type == "WAREHOUSE_BOTTLENECK"

    if cat == PlanCategory.FASTEST:
        port_recovered = "08:00 AM - 10:00 AM (ON TIME - Nominal Clearance)" if (is_road_disruption or is_whs_disruption) else f"⚡ 08:30 AM - 09:30 AM (Priority Crane Handling: {port_slot})"
        if is_whs_disruption:
            truck_recovered = "10:00 AM - 01:30 PM (ON TIME - Nominal Highway Transit)"
        else:
            truck_recovered = f"⚡ 09:30 AM (Emergency Relief Fleet Dispatched: {carrier_slot} - 0h Idle)"
        whs_recovered = f"⚡ 01:30 PM (Expedited Intake Bay Reserved: {whs_slot})"
        cust_recovered = "⚡ 04:30 PM Delivery Commitment (ON TIME - 30m Ahead of SLA Window!)"
    elif cat == PlanCategory.CHEAPEST:
        port_recovered = "08:00 AM - 10:00 AM (ON TIME - Nominal Clearance)" if (is_road_disruption or is_whs_disruption) else f"🟢 10:00 AM - 12:00 PM (Absorbs Delay at Standard Berth: {port_slot})"
        if is_whs_disruption:
            truck_recovered = "10:00 AM - 01:30 PM (ON TIME - Nominal Highway Transit)"
        else:
            truck_recovered = f"🟢 12:00 PM (Driver Realigned at Standby: {carrier_slot} - ₹0 Replacement Surcharge)"
        whs_recovered = f"🟢 04:00 PM (Shift Rescheduled to Off-Peak Window: {whs_slot} - ₹0 Forfeit)"
        cust_recovered = f"🟢 Arrival +{plan.total_delay_hours:.1f}h Offset (Saves ₹{cost_saved:,.0f} vs Demurrage Exposure)"
    else:  # SAFEST
        port_recovered = "08:00 AM - 10:00 AM (ON TIME - Nominal Clearance)" if (is_road_disruption or is_whs_disruption) else f"🛡️ 09:00 AM - 10:30 AM (Buffer Protected Berth Allocation: {port_slot})"
        if is_whs_disruption:
            truck_recovered = "10:00 AM - 01:30 PM (ON TIME - Nominal Highway Transit)"
        else:
            truck_recovered = f"🛡️ 10:30 AM (Protected Arterial Detour: {carrier_slot} - Dynamic Routing)"
        whs_recovered = f"🛡️ 02:30 PM (Protected Dock Slot Reserved: {whs_slot} - 100% Bay Clearance)"
        cust_recovered = f"🛡️ 05:00 PM Guaranteed Delivery (Exact SLA Met with {plan.reliability_score*100:.0f}% Buffer Reliability)"

    timeline_data = [
        {
            "Milestone": "1. ⚓ Port Berth Customs",
            "Nominal Baseline": "08:00 AM - 10:00 AM",
            "Disrupted Cascade (Unmitigated)": port_disrupted,
            f"FreightFlow AI [{cat.value}] Recovered": port_recovered
        },
        {
            "Milestone": "2. 🚛 Truck Fleet Dispatch",
            "Nominal Baseline": "10:00 AM Scheduled Pickup",
            "Disrupted Cascade (Unmitigated)": truck_disrupted,
            f"FreightFlow AI [{cat.value}] Recovered": truck_recovered
        },
        {
            "Milestone": "3. 🏬 Warehouse Dock Bay",
            "Nominal Baseline": "01:30 PM Intake Bay Slot",
            "Disrupted Cascade (Unmitigated)": whs_disrupted,
            f"FreightFlow AI [{cat.value}] Recovered": whs_recovered
        },
        {
            "Milestone": "4. 📦 Customer Delivery SLA",
            "Nominal Baseline": "05:00 PM Promised Delivery",
            "Disrupted Cascade (Unmitigated)": cust_disrupted,
            f"FreightFlow AI [{cat.value}] Recovered": cust_recovered
        }
    ]

    st.table(timeline_data)

    # Active allocation summary badge bar
    st.markdown(
        f"""
        <div style="background:rgba(128,128,128,0.06); border:1px solid rgba(128,128,128,0.2); border-radius:10px; padding:12px 18px; margin-top:14px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
            <div>
                <span style="font-weight:700; color:inherit;">Active Plan:</span> 
                <span style="font-weight:800; color:#38bdf8;">{cat.value}</span>
                <span style="margin-left:14px; font-weight:700; color:inherit;">Total Cost:</span> 
                <span style="font-weight:800; color:#22c55e;">₹{plan.total_cost_inr:,.0f}</span>
                <span style="margin-left:14px; font-weight:700; color:inherit;">Net Delay:</span> 
                <span style="font-weight:800; color:#f59e0b;">+{plan.total_delay_hours:.1f} hrs</span>
                <span style="margin-left:14px; font-weight:700; color:inherit;">Reliability:</span> 
                <span style="font-weight:800; color:#38bdf8;">{plan.reliability_score*100:.0f}%</span>
            </div>
            <div style="font-size:12px; color:inherit; opacity:0.85;">
                ⚓ <b>{port_slot}</b> &nbsp;|&nbsp; 🚛 <b>{carrier_slot}</b> &nbsp;|&nbsp; 🏬 <b>{whs_slot}</b>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
