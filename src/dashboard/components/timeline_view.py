"""Before vs After schedule comparison view."""

import streamlit as st


def render_timeline_view():
    """Renders before and after schedule comparison table/Gantt timeline."""
    st.markdown("### Operational Schedule: Before vs After")
    st.caption("Visualizing slot realignment to prevent cascaded bottlenecks.")

    data = {
        "Entity": ["Port Berth", "Truck Fleet", "Warehouse Bay", "Customer Delivery"],
        "Original Schedule": ["10:00 AM - 02:00 PM", "02:00 PM - 06:00 PM", "06:00 PM - 09:00 PM", "10:00 PM"],
        "Disrupted Cascade": ["02:00 PM - 06:00 PM", "06:00 PM - 10:00 PM", "MISSED SLOT", "DELAYED (NEXT DAY)"],
        "Recovered Schedule": ["02:00 PM - 05:30 PM", "05:30 PM - 09:00 PM", "09:00 PM - 11:30 PM (Buffer)", "11:45 PM (Same Day)"]
    }
    st.table(data)
