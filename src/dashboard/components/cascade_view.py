"""NetworkX cascade graph visualizer and ₹ at risk live counter."""

import streamlit as st
from datetime import datetime
import plotly.graph_objects as go
from src.cascade.impact_analyzer import compute_cascade_impact
from src.risk_engine.scorer import predict_risk
from src.common.schemas import DisruptionEvent, DisruptionType


def render_cascade_view():
    """Renders interactive disruption simulation, risk prediction, and cascade impact graph."""
    st.markdown("### 1. Ingest Disruption Telemetry")
    
    col_input1, col_input2, col_input3 = st.columns([2, 1, 1])
    with col_input1:
        shipment_id = st.selectbox(
            "Select Consignment / Shipment:",
            ["SHP-1005 (Flagship AutoParts Demo)", "SHP-1001", "SHP-1002", "SHP-1003", "SHP-1004"],
            index=0
        )
        actual_shp_id = shipment_id.split(" ")[0]
        
    with col_input2:
        delay_hours = st.slider("Port Berth Delay (Hours):", min_value=0.5, max_value=8.0, value=4.0, step=0.5)
        
    with col_input3:
        disruption_type = st.selectbox(
            "Disruption Event Type:",
            ["PORT_CONGESTION", "VESSEL_DELAY", "TRUCK_BREAKDOWN", "TRAFFIC_INCIDENT", "WAREHOUSE_BOTTLENECK"],
            index=0
        )

    if st.button("🚀 Analyze Disruption & Compute Cascade Impact", type="primary"):
        # Run ML Risk Scorer
        score, risk_level = predict_risk(actual_shp_id, new_delay_hours=delay_hours, congestion=0.75)
        
        # Run 4-Node Cascade Impact Analyzer
        impact = compute_cascade_impact(actual_shp_id, added_delay_hours=delay_hours)
        
        # Save to session state for other views
        st.session_state["current_impact"] = impact
        st.session_state["current_risk_score"] = score
        st.session_state["current_risk_level"] = risk_level
        st.session_state["current_shipment_id"] = actual_shp_id
        st.session_state["current_delay_hours"] = delay_hours
        st.session_state["current_disruption_type"] = disruption_type

    # Display results if available
    impact = st.session_state.get("current_impact")
    if impact:
        st.divider()
        st.markdown(f"### Disruption Analysis for `{st.session_state.get('current_shipment_id')}`")

        # Top Metric Cards
        risk_color = "red" if impact.risk_level in ("HIGH", "CRITICAL") else "orange"
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        with col_m1:
            st.metric("Risk Level", f"{impact.risk_level}", delta=f"Score: {st.session_state.get('current_risk_score', 0.85):.2f}")
        with col_m2:
            st.metric("Total ₹ at Risk", f"₹ {impact.financial_risk_inr:,.2f}", delta=f"CRITICAL Exposure", delta_color="inverse")
        with col_m3:
            st.metric("Cascaded Delay", f"+{impact.total_cascaded_delay_hours:.1f} hrs", delta="Downstream Impact")
        with col_m4:
            st.metric("Affected Milestones", f"{len(impact.nodes)} Nodes", delta="Breached")

        # 4-Node Cascade Visualizer Cards
        st.markdown("#### 4-Node Cascading Supply Chain Propagation")
        node_cols = st.columns(len(impact.nodes))
        icons = {"PORT": "🚢", "TRUCK": "🚛", "WAREHOUSE": "🏬", "CUSTOMER": "📦"}

        for idx, (node, col) in enumerate(zip(impact.nodes, node_cols)):
            with col:
                icon = icons.get(node.node_type, "📍")
                badge_color = "#ffebee" if node.status == "BREACHED" else ("#fff3e0" if node.status == "DELAYED" else "#e8f5e9")
                border_color = "#c62828" if node.status == "BREACHED" else ("#ef6c00" if node.status == "DELAYED" else "#2e7d32")
                
                st.markdown(
                    f"""
                    <div style="background-color: {badge_color}; border: 2px solid {border_color}; border-radius: 8px; padding: 12px; margin-bottom: 10px;">
                        <h4 style="margin:0 0 5px 0;">{icon} {node.node_type}</h4>
                        <p style="margin:0; font-weight:bold; color: {border_color};">Status: {node.status}</p>
                        <p style="margin:2px 0; font-size:13px;">Delay: <b>+{node.delay_hours:.1f} hrs</b></p>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                with st.expander(f"Details", expanded=False):
                    for k, v in node.details.items():
                        st.caption(f"• **{k}**: {v}")

        # Penalty Breakdown Table
        st.markdown("#### Downstream Financial Penalties (₹ at Risk Breakdown)")
        penalties = impact.penalty_breakdown or {}
        p_df = [
            {"Milestone / Penalty Type": k.replace("_", " ").title(), "Financial Damage": f"₹ {v:,.2f}"}
            for k, v in penalties.items()
        ]
        st.table(p_df)
    else:
        st.info("👆 Click **'Analyze Disruption & Compute Cascade Impact'** above to run the live pipeline on `SHP-1005`.")
