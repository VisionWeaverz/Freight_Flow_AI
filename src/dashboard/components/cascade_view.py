"""NetworkX cascade graph visualizer and ₹ at risk counter."""

import streamlit as st


def render_cascade_view():
    """Renders visual graph of supply chain nodes and downstream financial risk."""
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total ₹ at Risk", "₹ 2,45,000", delta="-₹ 1,80,000 upon recovery")
    with col2:
        st.metric("Downstream Bookings Impacted", "4 Bookings", delta="Critical")
    with col3:
        st.metric("Estimated Delay", "+3.5 Hours", delta="High Risk")

    st.info("Interactive NetworkX dependency graph will be rendered here.")
    # TODO: Connect with src/cascade/graph_builder.py and visualize with Plotly/PyVis
