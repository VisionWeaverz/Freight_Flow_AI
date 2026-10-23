"""NetworkX cascade graph visualizer and ₹ at risk live counter with Plotly pipeline."""

import streamlit as st
from datetime import datetime
import plotly.graph_objects as go
from src.cascade.impact_analyzer import compute_cascade_impact
from src.risk_engine.scorer import predict_risk


def build_plotly_cascade_diagram(nodes):
    """Draws an interactive horizontal pipeline diagram of the 4 cascading nodes."""
    x_pos = [1, 2.5, 4.0, 5.5]
    y_pos = [1, 1, 1, 1]
    
    node_colors = []
    node_symbols = []
    node_text = []
    hover_text = []

    color_map = {
        "BREACHED": "#ef4444",  # High-contrast Modern Red
        "DELAYED": "#f59e0b",   # Amber / Orange
        "ON_TIME": "#10b981",   # Forest Green
    }

    for node in nodes:
        c = color_map.get(node.status, "#64748b")
        node_colors.append(c)
        node_symbols.append("square")
        node_text.append(f"<b>{node.node_type}</b><br>{node.status}<br>(+{node.delay_hours:.1f}h)")
        hover_text.append(f"<b>{node.name}</b><br>Status: {node.status}<br>Delay: +{node.delay_hours:.1f}h")

    fig = go.Figure()

    # Add connecting arrows between the 4 nodes
    for i in range(len(x_pos) - 1):
        fig.add_annotation(
            x=x_pos[i+1] - 0.35, y=y_pos[i],
            ax=x_pos[i] + 0.35, ay=y_pos[i],
            xref="x", yref="y", axref="x", ayref="y",
            showarrow=True,
            arrowhead=3,
            arrowsize=1.5,
            arrowwidth=3,
            arrowcolor="#94a3b8"
        )

    # Add milestone node cards
    fig.add_trace(go.Scatter(
        x=x_pos,
        y=y_pos,
        mode="markers+text",
        marker=dict(
            size=64,
            color=node_colors,
            symbol="square",
            line=dict(width=2, color="rgba(255, 255, 255, 0.6)")
        ),
        text=node_text,
        textposition="middle center",
        textfont=dict(color="#ffffff", size=11, family="Inter, sans-serif"),
        hoverinfo="text",
        hovertext=hover_text
    ))

    fig.update_layout(
        height=180,
        margin=dict(l=20, r=20, t=10, b=10),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[0.4, 6.1]),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[0.7, 1.3]),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def render_cascade_view():
    """Renders interactive disruption simulation, risk prediction, and cascade impact graph."""
    
    # Preset quick-loader
    st.markdown("#### 🚢 Select Operational Consignment & Telemetry")
    col_input1, col_input2, col_input3, col_btn = st.columns([2, 1.2, 1.2, 1.2])

    with col_input1:
        shipment_id = st.selectbox(
            "Consignment ID:",
            ["SHP-1005 (Flagship AutoParts Demo)", "SHP-1001 (Electronics Whitefield)", "SHP-1002 (Textiles Tirupur)", "SHP-1003 (Auto Components Pune)", "SHP-1004 (Pharma Hyderabad)"],
            index=0
        )
        actual_shp_id = shipment_id.split(" ")[0]
        
    with col_input2:
        delay_hours = st.slider("Port Delay (Hours):", min_value=0.5, max_value=8.0, value=4.0, step=0.5)
        
    with col_input3:
        disruption_type = st.selectbox(
            "Disruption Type:",
            ["PORT_CONGESTION", "VESSEL_DELAY", "TRUCK_BREAKDOWN", "TRAFFIC_INCIDENT", "WAREHOUSE_BOTTLENECK"],
            index=0
        )

    with col_btn:
        st.write("")
        st.write("")
        trigger = st.button("⚡ Run Cascade Analysis", type="primary", use_container_width=True)

    # Default to SHP-1005 automatically on initial load if not computed yet
    if trigger or "current_impact" not in st.session_state:
        score, risk_level = predict_risk(actual_shp_id, new_delay_hours=delay_hours, congestion=0.75)
        impact = compute_cascade_impact(actual_shp_id, added_delay_hours=delay_hours)
        
        st.session_state["current_impact"] = impact
        st.session_state["current_risk_score"] = score
        st.session_state["current_risk_level"] = risk_level
        st.session_state["current_shipment_id"] = actual_shp_id
        st.session_state["current_delay_hours"] = delay_hours
        st.session_state["current_disruption_type"] = disruption_type

    impact = st.session_state.get("current_impact")
    if impact:
        st.divider()

        # Headline Metrics
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric(
                label="Predicted Delay Risk",
                value=f"{impact.risk_level}",
                delta=f"ML Probability: {st.session_state.get('current_risk_score', 0.85)*100:.0f}%",
                delta_color="inverse" if impact.risk_level in ("HIGH", "CRITICAL") else "normal"
            )
        with m2:
            st.metric(
                label="Total Financial ₹ at Risk",
                value=f"₹ {impact.financial_risk_inr:,.2f}",
                delta="Compounding Downstream Penalties",
                delta_color="inverse"
            )
        with m3:
            st.metric(
                label="Cascaded Total Delay",
                value=f"+{impact.total_cascaded_delay_hours:.1f} hrs",
                delta=f"Initial: +{impact.initial_delay_hours:.1f}h at Port",
                delta_color="inverse"
            )
        with m4:
            st.metric(
                label="Cascade Milestones",
                value=f"{len(impact.nodes)} Nodes Tracked",
                delta="Port ➔ Truck ➔ WH ➔ SLA"
            )

        # Plotly Diagram
        st.markdown("#### 🔗 4-Node Cascade Propagation Pipeline")
        fig = build_plotly_cascade_diagram(impact.nodes)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        # Milestone Details in Cards
        node_cols = st.columns(4)
        icons = {"PORT": "⚓", "TRUCK": "🚛", "WAREHOUSE": "🏬", "CUSTOMER": "📦"}
        for node, col in zip(impact.nodes, node_cols):
            with col:
                is_brk = node.status == "BREACHED"
                is_ontime = node.status == "ON_TIME"
                if is_brk:
                    bg_color = "rgba(239, 68, 68, 0.12)"
                    border_color = "rgba(239, 68, 68, 0.45)"
                    tag_color = "#ef4444"
                elif is_ontime:
                    bg_color = "rgba(34, 197, 94, 0.12)"
                    border_color = "rgba(34, 197, 94, 0.45)"
                    tag_color = "#22c55e"
                else:  # DELAYED
                    bg_color = "rgba(245, 158, 11, 0.12)"
                    border_color = "rgba(245, 158, 11, 0.45)"
                    tag_color = "#f59e0b"

                st.markdown(
                    f"""
                    <div style="background:{bg_color}; border:1.5px solid {border_color}; border-radius:10px; padding:12px 14px; margin-bottom:8px; box-shadow:0 2px 6px rgba(0,0,0,0.06);">
                        <div style="font-size:12px; font-weight:700; color:{tag_color}; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:4px;">
                            {icons.get(node.node_type, '📍')} {node.node_type}
                        </div>
                        <div style="font-size:18px; font-weight:800; color:inherit; margin:4px 0;">
                            {node.status}
                        </div>
                        <div style="font-size:12px; color:inherit; opacity:0.8;">
                            Delay: <b>+{node.delay_hours:.1f}h</b>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

        # Penalties Table & Details
        st.markdown("#### 💰 Downstream Financial Penalty Breakdown")
        penalties = impact.penalty_breakdown or {}
        p_df = [
            {"Milestone / Penalty Surcharge": k.replace("_", " ").title(), "Financial Exposure (INR)": f"₹ {v:,.2f}"}
            for k, v in penalties.items()
        ]
        st.dataframe(p_df, use_container_width=True, hide_index=True)
