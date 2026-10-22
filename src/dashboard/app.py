"""FreightFlow AI - Streamlit Dashboard Entry Point."""

import streamlit as st
from src.dashboard.components.cascade_view import render_cascade_view
from src.dashboard.components.plan_comparator import render_plan_comparator
from src.dashboard.components.human_approval import render_human_approval
from src.dashboard.components.timeline_view import render_timeline_view
from src.dashboard.components.metrics_view import render_metrics_view

st.set_page_config(
    page_title="FreightFlow AI - Disruption Prediction & Recovery",
    page_icon="🚢",
    layout="wide"
)

def main():
    st.title("🚢 FreightFlow AI: Disruption Prediction & Recovery")
    st.caption("Cross-party autonomous logistics coordination powered by multi-agent negotiation.")

    st.sidebar.header("Navigation")
    view_mode = st.sidebar.radio(
        "Select View",
        ["Live Operations & Cascade", "Negotiation & Recovery Plans", "Simulation Benchmarks"]
    )

    if view_mode == "Live Operations & Cascade":
        st.subheader("Disruption Monitoring & Cascade Impact Graph")
        render_cascade_view()
    elif view_mode == "Negotiation & Recovery Plans":
        st.subheader("Autonomous Negotiation & Recovery Plans")
        render_plan_comparator()
        render_human_approval()
        render_timeline_view()
    elif view_mode == "Simulation Benchmarks":
        st.subheader("50-Run Simulation & Feasibility Benchmarks")
        render_metrics_view()

if __name__ == "__main__":
    main()
