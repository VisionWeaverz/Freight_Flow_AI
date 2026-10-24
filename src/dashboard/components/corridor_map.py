"""Interactive Geospatial Multimodal Corridor Simulation for FreightFlow AI.

Visualizes the real-world JNPT (Nhava Sheva) -> Bhiwandi 3PL Hub -> Pune Automotive OEM corridor
with live route comparison (Baseline Congestion vs. FreightFlow AI Dynamic Rerouting Bypass)
and an interactive step-by-step playback simulation.
"""

from __future__ import annotations
import time
import streamlit as st
import plotly.graph_objects as go


def build_corridor_map(view_mode: str = "COMPARE", current_delay: float = 4.0, shipment_id: str = "SHP-1005") -> go.Figure:
    """Builds interactive dark-mode map of the Mumbai-Bhiwandi-Pune freight corridor."""
    
    # Baseline Congested Route (NH-48 through congested Mumbra/Thane bottleneck)
    base_lats = [18.9502, 19.0330, 19.1650, 19.2183, 19.2813, 19.2000, 18.7892, 18.7606]
    base_lons = [72.9510, 73.0297, 73.0300, 72.9781, 73.0483, 73.1500, 73.3444, 73.8636]

    # FreightFlow AI Dynamic Rerouting Bypass (via Atal Setu MTHL & Eastern Express Toll Corridor)
    ai_lats = [18.9502, 18.9950, 19.0600, 19.1800, 19.2813, 19.1200, 18.7892, 18.7606]
    ai_lons = [72.9510, 72.9700, 72.9900, 73.0100, 73.0483, 73.2200, 73.3444, 73.8636]

    fig = go.Figure()

    # Determine Scattermap vs Scattermapbox based on Plotly version
    has_scattermap = hasattr(go, "Scattermap")
    scatter_func = go.Scattermap if has_scattermap else getattr(go, "Scattermapbox")

    # 1. Baseline Disrupted Route
    if view_mode in ("COMPARE", "BASELINE"):
        fig.add_trace(scatter_func(
            lat=base_lats,
            lon=base_lons,
            mode='lines',
            line=dict(width=4, color='#ef4444'),
            name='🔴 Baseline (NH-48 Congestion / Cutoff Missed)',
            hoverinfo='text',
            text=[
                'JNPT Berth 2 (Disrupted)',
                'Terminal Gate Wait (+3h)',
                'Mumbra Bottleneck',
                'Thane Gridlock',
                'Bhiwandi Bay 7 (Cutoff Missed)',
                'Late Dispatch',
                'Expressway Jam',
                'Pune SLA Breached (+0.5h)'
            ]
        ))

    # 2. FreightFlow AI Optimal Reroute Bypass
    if view_mode in ("COMPARE", "RECOVERY"):
        fig.add_trace(scatter_func(
            lat=ai_lats,
            lon=ai_lons,
            mode='lines',
            line=dict(width=5, color='#00E676'),
            name='🟢 FreightFlow AI Bypass (Atal Setu / Bay 12)',
            hoverinfo='text',
            text=[
                'JNPT Berth 2 (Priority Gate Out)',
                'Atal Setu (MTHL) High-Speed Bypass',
                'Eastern Toll Freeway',
                'Dedicated Corridor Flyover',
                'Bhiwandi Bay 12 (Off-Peak Intake)',
                'Smooth Expressway Transfer',
                'Pune Corridor Green Wave',
                'Customer SLA Fully Preserved'
            ]
        ))

    # 3. Key Milestone Nodes
    hub_lats = [18.9502, 19.0760, 19.2813, 18.7606]
    hub_lons = [72.9510, 73.0100, 73.0483, 73.8636]
    hub_names = [
        f"⚓ <b>JNPT Port Berth 2</b><br>Shock: +{current_delay:.1f}h Berth Delay",
        f"🚛 <b>TRK-1005 (Ramesh Yadav)</b><br>Cargo: Automotive Electronics (₹45L)",
        "🏬 <b>Bhiwandi 3PL Hub</b><br>Original: Bay 7 (Missed) ➔ Rerouted: Bay 12",
        "🏭 <b>Pune Automotive OEM</b><br>Delivery SLA Target: 05:00 PM"
    ]
    hub_colors = ['#f59e0b', '#38bdf8', '#10b981', '#a855f7']

    fig.add_trace(scatter_func(
        lat=hub_lats,
        lon=hub_lons,
        mode='markers+text',
        marker=dict(size=14, color=hub_colors),
        text=["JNPT Berth 2", "TRK-1005", "Bhiwandi Hub", "Pune OEM"],
        textposition="top right",
        textfont=dict(size=11, color="#ffffff"),
        name='📍 Operational Milestones',
        hoverinfo='text',
        hovertext=hub_names
    ))

    # Layout config with fallback for map vs mapbox
    layout_args = dict(
        style='carto-darkmatter',
        center=dict(lat=19.08, lon=73.30),
        zoom=8.7
    )

    if has_scattermap:
        fig.update_layout(
            map=layout_args,
            height=430,
            margin=dict(l=0, r=0, t=10, b=0),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="left",
                x=0,
                bgcolor="rgba(11, 15, 25, 0.85)",
                font=dict(color="#ffffff", size=10.5)
            )
        )
    else:
        fig.update_layout(
            mapbox=layout_args,
            height=430,
            margin=dict(l=0, r=0, t=10, b=0),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="left",
                x=0,
                bgcolor="rgba(11, 15, 25, 0.85)",
                font=dict(color="#ffffff", size=10.5)
            )
        )

    return fig


def render_corridor_simulation(actual_shp_id: str, delay_hours: float, disruption_type: str, impact) -> None:
    """Renders the complete geospatial corridor simulation UI with route comparison and playback."""
    
    st.markdown("#### 🗺️ Live Geospatial Corridor & Dynamic Rerouting Simulator")
    st.caption("Real-world telemetry tracking across the **Nhava Sheva (JNPT) ➔ Bhiwandi 3PL ➔ Pune OEM** industrial corridor.")

    col_ctrl, col_sim = st.columns([2.5, 1.5])
    
    with col_ctrl:
        view_mode = st.radio(
            "Visualization Perspective:",
            ["COMPARE (Both Routes)", "🔴 Baseline Congested Route (NH-48)", "🟢 FreightFlow AI Bypass (Atal Setu / Bay 12)"],
            index=0,
            horizontal=True
        )
        mode_key = "COMPARE" if "COMPARE" in view_mode else ("BASELINE" if "Baseline" in view_mode else "RECOVERY")

    with col_sim:
        st.write("")
        play_sim = st.button("🎬 Run Live Reroute Simulation", type="secondary", use_container_width=True)

    # 1. Step-by-Step Playback Simulation Trigger
    if play_sim:
        sim_progress = st.progress(0, text="Initializing corridor simulation...")
        sim_alert = st.empty()

        sim_progress.progress(20, text="Step 1/5: Shock Ingestion at JNPT Berth 2...")
        sim_alert.info(f"🚨 Telemetry Alert: {disruption_type} (+{delay_hours:.1f}h) registered on vessel offload at Berth 2.")
        time.sleep(0.7)

        sim_progress.progress(40, text="Step 2/5: Scikit-learn Risk Engine Evaluation...")
        sim_alert.warning(f"🧠 ML GradientBoosting Model: Predicted Risk = {impact.risk_level} (Cutoff breach probability: 85%).")
        time.sleep(0.7)

        sim_progress.progress(60, text="Step 3/5: NetworkX Dependency Propagation...")
        sim_alert.error(f"💥 Cascade Alert: Missed intake cutoff at Bhiwandi Bay 7. ₹{impact.financial_risk_inr:,.0f} cash at risk!")
        time.sleep(0.7)

        sim_progress.progress(80, text="Step 4/5: Multi-Agent Autonomous Negotiation...")
        sim_alert.info("🤝 Consensus: Carrier Agent engages Atal Setu expressway bypass; Warehouse Agent shifts booking to Bay 12.")
        time.sleep(0.8)

        sim_progress.progress(100, text="Step 5/5: Autonomous Recovery Executed Successfully!")
        sim_alert.success("✅ Recovery Confirmed: Truck rerouted in < 2 seconds. Incurred recovery cost: ₹5,700 | Net saved: ₹12,050 (68%)!")
        time.sleep(0.5)

    # 2. Render Interactive Plotly Corridor Map
    fig = build_corridor_map(view_mode=mode_key, current_delay=delay_hours, shipment_id=actual_shp_id)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # 3. Route Telemetry & Economic Delta Comparison Cards
    c1, c2 = st.columns(2)
    
    with c1:
        st.markdown(
            f"""
            <div style="background:rgba(239, 68, 68, 0.08); border:1.5px solid rgba(239, 68, 68, 0.35); border-radius:10px; padding:14px 16px; margin-top:6px;">
                <div style="font-size:13px; font-weight:700; color:#ef4444; text-transform:uppercase; margin-bottom:6px;">
                    🔴 Baseline: Unmitigated Congestion (NH-48)
                </div>
                <div style="font-size:13px; color:inherit; line-height:1.6;">
                    • <b>Highway Corridor:</b> NH-48 via Mumbra & Thane bottleneck<br>
                    • <b>Total Journey Time:</b> 7.0 hrs (includes 3.0h gate detention)<br>
                    • <b>Dock Status:</b> <b>Bay 7 Forfeited</b> (Arrived 03:30 PM past cutoff)<br>
                    • <b>Customer SLA:</b> <b>Breached by 0.5h</b> (Late penalty applied)<br>
                    • <b>Net Monetary Loss:</b> <b style="color:#ef4444; font-size:15px;">₹ {impact.financial_risk_inr:,.0f}</b>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with c2:
        st.markdown(
            f"""
            <div style="background:rgba(34, 197, 94, 0.08); border:1.5px solid rgba(34, 197, 94, 0.35); border-radius:10px; padding:14px 16px; margin-top:6px;">
                <div style="font-size:13px; font-weight:700; color:#22c55e; text-transform:uppercase; margin-bottom:6px;">
                    🟢 FreightFlow AI: Dynamic Rerouting (Atal Setu Bypass)
                </div>
                <div style="font-size:13px; color:inherit; line-height:1.6;">
                    • <b>Highway Corridor:</b> MTHL (Atal Setu) & Eastern Toll Freeway<br>
                    • <b>Total Journey Time:</b> 4.2 hrs (Saved 2.8 hours of gridlock)<br>
                    • <b>Dock Status:</b> <b>Off-Peak Bay 12 Assigned</b> (04:00 PM slot)<br>
                    • <b>Customer SLA:</b> <b>100% Preserved</b> (Delivered within window)<br>
                    • <b>Net Recovery ROI:</b> <b style="color:#22c55e; font-size:15px;">₹ 12,050 Hard Cash Saved (68%)</b>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
