"""Before vs After schedule comparison view."""

import streamlit as st
from datetime import datetime, timedelta


def render_timeline_view():
    """Renders before and after schedule comparison table/timeline."""
    st.markdown("### 4. Schedule Realignment: Before vs. Disrupted vs. Recovered")
    st.caption("Visualizes milestone recovery to eliminate cascading supply chain failure.")

    plan = st.session_state.get("selected_plan")
    base_time = datetime(2026, 10, 23, 8, 0, 0)

    carrier_slot = plan.carrier_slot_id if plan else "TRUCK-SLOT-SAFEST"
    port_slot = plan.port_slot_id if plan else "BERTH-BUFFERED"
    whs_slot = plan.warehouse_slot_id if plan else "DOCK-BAY-RESERVED"

    timeline_data = [
        {
            "Milestone": "1. Port Berth Customs",
            "Nominal Schedule": "08:00 AM - 09:00 AM",
            "Disrupted Cascade (Unmitigated)": "12:00 PM - 01:00 PM (+4.0h Delay)",
            "FreightFlow AI Recovered": f"10:00 AM - 11:30 AM ({port_slot})"
        },
        {
            "Milestone": "2. Truck Fleet Dispatch",
            "Nominal Schedule": "09:00 AM Pickup",
            "Disrupted Cascade (Unmitigated)": "01:00 PM (Driver Idle 3.0h - BREACHED)",
            "FreightFlow AI Recovered": f"11:30 AM (Driver Zero Idle - {carrier_slot})"
        },
        {
            "Milestone": "3. Warehouse Dock Bay",
            "Nominal Schedule": "01:30 PM Slot",
            "Disrupted Cascade (Unmitigated)": "04:30 PM (Missed Grace - BREACHED)",
            "FreightFlow AI Recovered": f"03:00 PM Slot Realignment ({whs_slot})"
        },
        {
            "Milestone": "4. Customer Delivery SLA",
            "Nominal Schedule": "05:00 PM Promised",
            "Disrupted Cascade (Unmitigated)": "06:30 PM (SLA Fine - BREACHED)",
            "FreightFlow AI Recovered": "04:50 PM Delivery (On Time SLA Preserved)"
        }
    ]

    st.table(timeline_data)
