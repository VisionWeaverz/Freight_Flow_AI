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
        border = "#16a34a" if is_sel else "#cbd5e1"
        bg = "#f0fdf4" if is_sel else "#ffffff"
        st.markdown(
            f"""
            <div style="background:{bg}; border:2px solid {border}; border-radius:12px; padding:16px; margin-bottom:12px; box-shadow:0 4px 6px -1px rgba(0,0,0,0.05);">
                <span style="background:#dcfce7; color:#15803d; font-size:11px; font-weight:700; padding:3px 8px; border-radius:12px;">COST OPTIMIZED</span>
                <h3 style="margin:8px 0 4px 0; color:#14532d;">🟢 Cheapest Plan</h3>
                <div style="font-size:26px; font-weight:800; color:#0f172a;">₹ {cheapest.total_cost_inr:,.0f}</div>
                <p style="font-size:13px; color:#64748b; margin:2px 0 12px 0;">Saves ₹{max(0, impact.financial_risk_inr - cheapest.total_cost_inr):,.0f} vs. Disruption Damage</p>
                <div style="border-top:1px solid #e2e8f0; padding-top:10px; font-size:13px;">
                    <p style="margin:4px 0;">⏱️ <b>Added Delay:</b> +{cheapest.total_delay_hours:.1f} hrs</p>
                    <p style="margin:4px 0;">🛡️ <b>Reliability:</b> {cheapest.reliability_score * 100:.0f}%</p>
                    <p style="margin:4px 0;">🚛 <b>Truck:</b> {cheapest.carrier_slot_id}</p>
                    <p style="margin:4px 0;">🏬 <b>Dock:</b> {cheapest.warehouse_slot_id}</p>
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
        border = "#0284c7" if is_sel else "#cbd5e1"
        bg = "#f0f9ff" if is_sel else "#ffffff"
        st.markdown(
            f"""
            <div style="background:{bg}; border:2px solid {border}; border-radius:12px; padding:16px; margin-bottom:12px; box-shadow:0 4px 6px -1px rgba(0,0,0,0.05);">
                <span style="background:#e0f2fe; color:#0369a1; font-size:11px; font-weight:700; padding:3px 8px; border-radius:12px;">SPEED PRIORITY</span>
                <h3 style="margin:8px 0 4px 0; color:#0c4a6e;">⚡ Fastest Plan</h3>
                <div style="font-size:26px; font-weight:800; color:#0f172a;">₹ {fastest.total_cost_inr:,.0f}</div>
                <p style="font-size:13px; color:#64748b; margin:2px 0 12px 0;">Immediate Velocity Recovery</p>
                <div style="border-top:1px solid #e2e8f0; padding-top:10px; font-size:13px;">
                    <p style="margin:4px 0;">⏱️ <b>Added Delay:</b> +{fastest.total_delay_hours:.1f} hrs (0h Extra!)</p>
                    <p style="margin:4px 0;">🛡️ <b>Reliability:</b> {fastest.reliability_score * 100:.0f}%</p>
                    <p style="margin:4px 0;">🚛 <b>Truck:</b> {fastest.carrier_slot_id}</p>
                    <p style="margin:4px 0;">🏬 <b>Dock:</b> {fastest.warehouse_slot_id}</p>
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
        border = "#d97706" if is_sel else "#cbd5e1"
        bg = "#fffbeb" if is_sel else "#ffffff"
        st.markdown(
            f"""
            <div style="background:{bg}; border:2px solid {border}; border-radius:12px; padding:16px; margin-bottom:12px; box-shadow:0 4px 6px -1px rgba(0,0,0,0.05);">
                <span style="background:#fef3c7; color:#b45309; font-size:11px; font-weight:700; padding:3px 8px; border-radius:12px;">RECOMMENDED</span>
                <h3 style="margin:8px 0 4px 0; color:#78350f;">🛡️ Safest Plan</h3>
                <div style="font-size:26px; font-weight:800; color:#0f172a;">₹ {safest.total_cost_inr:,.0f}</div>
                <p style="font-size:13px; color:#64748b; margin:2px 0 12px 0;">Maximum On-Time Resilience</p>
                <div style="border-top:1px solid #e2e8f0; padding-top:10px; font-size:13px;">
                    <p style="margin:4px 0;">⏱️ <b>Added Delay:</b> Shift Realignment</p>
                    <p style="margin:4px 0;">🛡️ <b>Reliability:</b> {safest.reliability_score * 100:.0f}% (Highest)</p>
                    <p style="margin:4px 0;">🚛 <b>Truck:</b> {safest.carrier_slot_id}</p>
                    <p style="margin:4px 0;">🏬 <b>Dock:</b> {safest.warehouse_slot_id}</p>
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
