"""Side-by-side comparison of Top 3 recovery plans (Cheapest, Fastest, Safest)."""

import streamlit as st
from src.agents.coordinator import CentralCoordinator
from src.cascade.impact_analyzer import compute_cascade_impact
from src.common.schemas import PlanCategory


def render_plan_comparator():
    """Renders trade-off comparison between Cheapest, Fastest, and Safest plans."""
    impact = st.session_state.get("current_impact")
    if not impact:
        impact = compute_cascade_impact("SHP-1005", added_delay_hours=4.0)
        st.session_state["current_impact"] = impact
        st.session_state["current_shipment_id"] = "SHP-1005"

    coordinator = CentralCoordinator()
    plans = coordinator.run_recovery_negotiation(impact)
    st.session_state["negotiated_plans"] = plans

    st.markdown("#### 🤝 Autonomous Multi-Agent Negotiation Outcomes")
    st.caption("The Central Coordinator resolved 3 rounds between Port, Carrier, and Warehouse agents, producing 3 non-dominated Pareto alternatives:")

    cheapest = next((p for p in plans if p.category == PlanCategory.CHEAPEST), plans[0])
    fastest = next((p for p in plans if p.category == PlanCategory.FASTEST), plans[1] if len(plans) > 1 else plans[0])
    safest = next((p for p in plans if p.category == PlanCategory.SAFEST), plans[2] if len(plans) > 2 else plans[0])

    selected_category = st.session_state.get("selected_plan_category", PlanCategory.SAFEST.value)

    col1, col2, col3 = st.columns(3)

    # Card 1: Cheapest Plan
    with col1:
        is_sel = selected_category == PlanCategory.CHEAPEST.value
        border = "#22c55e" if is_sel else "rgba(128, 128, 128, 0.25)"
        bg = "rgba(34, 197, 94, 0.12)" if is_sel else "var(--secondary-background-color, rgba(128, 128, 128, 0.06))"
        st.markdown(
            f"""
            <div style="background:{bg}; border:2px solid {border}; border-radius:12px; padding:16px; margin-bottom:12px; box-shadow:0 4px 6px -1px rgba(0,0,0,0.05);">
                <span style="background:rgba(34, 197, 94, 0.18); color:#22c55e; border:1px solid rgba(34, 197, 94, 0.35); font-size:11px; font-weight:700; padding:3px 8px; border-radius:12px;">COST OPTIMIZED</span>
                <h3 style="margin:8px 0 4px 0; color:#22c55e;">🟢 Cheapest Plan</h3>
                <div style="font-size:26px; font-weight:800; color:var(--text-color, #0f172a);">₹ {cheapest.total_cost_inr:,.0f}</div>
                <p style="font-size:13px; color:var(--text-color, #64748b); opacity:0.8; margin:2px 0 12px 0;">Saves ₹{max(0, impact.financial_risk_inr - cheapest.total_cost_inr):,.0f} vs. Disruption Damage</p>
                <div style="border-top:1px solid rgba(128, 128, 128, 0.2); padding-top:10px; font-size:13px; color:var(--text-color, #334155);">
                    <p style="margin:4px 0; color:var(--text-color, #334155);">⏱️ <b>Added Delay:</b> +{cheapest.total_delay_hours:.1f} hrs</p>
                    <p style="margin:4px 0; color:var(--text-color, #334155);">🛡️ <b>Reliability:</b> {cheapest.reliability_score * 100:.0f}%</p>
                    <p style="margin:4px 0; color:var(--text-color, #334155);">🚛 <b>Truck:</b> {cheapest.carrier_slot_id}</p>
                    <p style="margin:4px 0; color:var(--text-color, #334155);">🏬 <b>Dock:</b> {cheapest.warehouse_slot_id}</p>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        if st.button("Select Cheapest Plan", key="btn_cheapest", use_container_width=True, type="secondary" if not is_sel else "primary"):
            st.session_state["selected_plan_category"] = PlanCategory.CHEAPEST.value
            st.session_state["selected_plan"] = cheapest
            st.rerun()

    # Card 2: Fastest Plan
    with col2:
        is_sel = selected_category == PlanCategory.FASTEST.value
        border = "#0ea5e9" if is_sel else "rgba(128, 128, 128, 0.25)"
        bg = "rgba(14, 165, 233, 0.12)" if is_sel else "var(--secondary-background-color, rgba(128, 128, 128, 0.06))"
        st.markdown(
            f"""
            <div style="background:{bg}; border:2px solid {border}; border-radius:12px; padding:16px; margin-bottom:12px; box-shadow:0 4px 6px -1px rgba(0,0,0,0.05);">
                <span style="background:rgba(14, 165, 233, 0.18); color:#0ea5e9; border:1px solid rgba(14, 165, 233, 0.35); font-size:11px; font-weight:700; padding:3px 8px; border-radius:12px;">SPEED PRIORITY</span>
                <h3 style="margin:8px 0 4px 0; color:#0ea5e9;">⚡ Fastest Plan</h3>
                <div style="font-size:26px; font-weight:800; color:var(--text-color, #0f172a);">₹ {fastest.total_cost_inr:,.0f}</div>
                <p style="font-size:13px; color:var(--text-color, #64748b); opacity:0.8; margin:2px 0 12px 0;">Immediate Velocity Recovery</p>
                <div style="border-top:1px solid rgba(128, 128, 128, 0.2); padding-top:10px; font-size:13px; color:var(--text-color, #334155);">
                    <p style="margin:4px 0; color:var(--text-color, #334155);">⏱️ <b>Added Delay:</b> +{fastest.total_delay_hours:.1f} hrs (0h Extra!)</p>
                    <p style="margin:4px 0; color:var(--text-color, #334155);">🛡️ <b>Reliability:</b> {fastest.reliability_score * 100:.0f}%</p>
                    <p style="margin:4px 0; color:var(--text-color, #334155);">🚛 <b>Truck:</b> {fastest.carrier_slot_id}</p>
                    <p style="margin:4px 0; color:var(--text-color, #334155);">🏬 <b>Dock:</b> {fastest.warehouse_slot_id}</p>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        if st.button("Select Fastest Plan", key="btn_fastest", use_container_width=True, type="secondary" if not is_sel else "primary"):
            st.session_state["selected_plan_category"] = PlanCategory.FASTEST.value
            st.session_state["selected_plan"] = fastest
            st.rerun()

    # Card 3: Safest Plan
    with col3:
        is_sel = selected_category == PlanCategory.SAFEST.value
        border = "#f59e0b" if is_sel else "rgba(128, 128, 128, 0.25)"
        bg = "rgba(245, 158, 11, 0.12)" if is_sel else "var(--secondary-background-color, rgba(128, 128, 128, 0.06))"
        st.markdown(
            f"""
            <div style="background:{bg}; border:2px solid {border}; border-radius:12px; padding:16px; margin-bottom:12px; box-shadow:0 4px 6px -1px rgba(0,0,0,0.05);">
                <span style="background:rgba(245, 158, 11, 0.18); color:#f59e0b; border:1px solid rgba(245, 158, 11, 0.35); font-size:11px; font-weight:700; padding:3px 8px; border-radius:12px;">RECOMMENDED</span>
                <h3 style="margin:8px 0 4px 0; color:#f59e0b;">🛡️ Safest Plan</h3>
                <div style="font-size:26px; font-weight:800; color:var(--text-color, #0f172a);">₹ {safest.total_cost_inr:,.0f}</div>
                <p style="font-size:13px; color:var(--text-color, #64748b); opacity:0.8; margin:2px 0 12px 0;">Maximum On-Time Resilience</p>
                <div style="border-top:1px solid rgba(128, 128, 128, 0.2); padding-top:10px; font-size:13px; color:var(--text-color, #334155);">
                    <p style="margin:4px 0; color:var(--text-color, #334155);">⏱️ <b>Added Delay:</b> Shift Realignment</p>
                    <p style="margin:4px 0; color:var(--text-color, #334155);">🛡️ <b>Reliability:</b> {safest.reliability_score * 100:.0f}% (Highest)</p>
                    <p style="margin:4px 0; color:var(--text-color, #334155);">🚛 <b>Truck:</b> {safest.carrier_slot_id}</p>
                    <p style="margin:4px 0; color:var(--text-color, #334155);">🏬 <b>Dock:</b> {safest.warehouse_slot_id}</p>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        if st.button("Select Safest Plan", key="btn_safest", use_container_width=True, type="secondary" if not is_sel else "primary"):
            st.session_state["selected_plan_category"] = PlanCategory.SAFEST.value
            st.session_state["selected_plan"] = safest
            st.rerun()

    # Ensure selected plan defaults to Safest
    if "selected_plan" not in st.session_state:
        st.session_state["selected_plan"] = safest
        st.session_state["selected_plan_category"] = PlanCategory.SAFEST.value
