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

    # Active Disruption Context Pill linking Tab 1 to Tab 2
    shipment_id = st.session_state.get("current_shipment_id", "SHP-1005")
    disruption_type = st.session_state.get("current_disruption_type", "PORT_CONGESTION")
    delay_hours = getattr(impact, "initial_delay_hours", 4.0)
    risk_inr = getattr(impact, "financial_risk_inr", 17750.0)

    st.markdown(
        f"""
        <div style="background:rgba(2, 132, 199, 0.08); border:1.5px solid rgba(2, 132, 199, 0.3); border-radius:10px; padding:10px 16px; margin-bottom:14px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
            <div>
                <span style="font-size:11px; font-weight:700; color:#0284c7; text-transform:uppercase; letter-spacing:0.5px;">🎯 Active Target (from Tab 1):</span>
                <span style="font-size:14px; font-weight:800; margin-left:6px;">{shipment_id}</span>
                <span style="font-size:13px; opacity:0.85; margin-left:8px;">• {disruption_type.replace('_', ' ').title()} (+{delay_hours:.1f}h)</span>
            </div>
            <div>
                <span style="font-size:12px; opacity:0.8;">Baseline Unmitigated Damage:</span>
                <span style="font-size:14px; font-weight:800; color:#ef4444; margin-left:6px;">₹{risk_inr:,.0f}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("#### 🤝 Autonomous Multi-Agent Negotiation Outcomes")
    st.caption("The Central Coordinator resolved 3 rounds between Port, Carrier, and Warehouse agents, producing 3 non-dominated Pareto alternatives:")

    cheapest = next((p for p in plans if p.category == PlanCategory.CHEAPEST), plans[0])
    fastest = next((p for p in plans if p.category == PlanCategory.FASTEST), plans[1] if len(plans) > 1 else plans[0])
    safest = next((p for p in plans if p.category == PlanCategory.SAFEST), plans[2] if len(plans) > 2 else plans[0])

    plans_by_cat = {
        PlanCategory.CHEAPEST.value: cheapest,
        PlanCategory.FASTEST.value: fastest,
        PlanCategory.SAFEST.value: safest,
    }

    selected_category = st.session_state.get("selected_plan_category", PlanCategory.SAFEST.value)
    if selected_category not in plans_by_cat:
        selected_category = PlanCategory.SAFEST.value

    # Keep selected_plan synchronized with the active category on every render
    st.session_state["selected_plan_category"] = selected_category
    st.session_state["selected_plan"] = plans_by_cat[selected_category]

    col1, col2, col3 = st.columns(3)

    # Card 1: Cheapest Plan
    with col1:
        is_sel = selected_category == PlanCategory.CHEAPEST.value
        border = "#22c55e" if is_sel else "rgba(128, 128, 128, 0.25)"
        bg = "rgba(34, 197, 94, 0.12)" if is_sel else "rgba(128, 128, 128, 0.08)"
        st.markdown(
            f"""
            <div style="background:{bg}; border:2px solid {border}; border-radius:12px; padding:16px; margin-bottom:12px; box-shadow:0 4px 6px -1px rgba(0,0,0,0.05);">
                <span style="background:rgba(34, 197, 94, 0.18); color:#22c55e; border:1px solid rgba(34, 197, 94, 0.35); font-size:11px; font-weight:700; padding:3px 8px; border-radius:12px;">COST OPTIMIZED</span>
                <h3 style="margin:8px 0 4px 0; color:#22c55e;">🟢 Cheapest Plan</h3>
                <div style="font-size:26px; font-weight:800; color:inherit;">₹ {cheapest.total_cost_inr:,.0f}</div>
                <p style="font-size:13px; color:inherit; opacity:0.75; margin:2px 0 12px 0;">Saves ₹{max(0, impact.financial_risk_inr - cheapest.total_cost_inr):,.0f} vs. Disruption Damage</p>
                <div style="border-top:1px solid rgba(128, 128, 128, 0.2); padding-top:10px; font-size:13px; color:inherit;">
                    <p style="margin:4px 0; color:inherit;">⏱️ <b>Added Delay:</b> +{cheapest.total_delay_hours:.1f} hrs</p>
                    <p style="margin:4px 0; color:inherit;">🛡️ <b>Reliability:</b> {cheapest.reliability_score * 100:.0f}%</p>
                    <p style="margin:4px 0; color:inherit;">🚛 <b>Truck:</b> Standby ({cheapest.carrier_slot_id})</p>
                    <p style="margin:4px 0; color:inherit;">🏬 <b>Dock:</b> Off-Peak ({cheapest.warehouse_slot_id})</p>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        if st.button("Select Cheapest Plan", key="btn_cheapest", use_container_width=True, type="secondary" if not is_sel else "primary"):
            st.session_state["selected_plan_category"] = PlanCategory.CHEAPEST.value
            st.session_state["selected_plan"] = cheapest
            st.session_state["force_regenerate_explanation"] = True
            st.rerun()

    # Card 2: Fastest Plan
    with col2:
        is_sel = selected_category == PlanCategory.FASTEST.value
        border = "#0ea5e9" if is_sel else "rgba(128, 128, 128, 0.25)"
        bg = "rgba(14, 165, 233, 0.12)" if is_sel else "rgba(128, 128, 128, 0.08)"
        disruption_delay = getattr(impact, "initial_delay_hours", 4.0)
        time_mitigated = max(0.0, disruption_delay - fastest.total_delay_hours)
        mitigated_tag = f"({time_mitigated:.1f}h Mitigated!)" if time_mitigated > 0 else "(Priority Speed)"
        st.markdown(
            f"""
            <div style="background:{bg}; border:2px solid {border}; border-radius:12px; padding:16px; margin-bottom:12px; box-shadow:0 4px 6px -1px rgba(0,0,0,0.05);">
                <span style="background:rgba(14, 165, 233, 0.18); color:#0ea5e9; border:1px solid rgba(14, 165, 233, 0.35); font-size:11px; font-weight:700; padding:3px 8px; border-radius:12px;">SPEED PRIORITY</span>
                <h3 style="margin:8px 0 4px 0; color:#0ea5e9;">⚡ Fastest Plan</h3>
                <div style="font-size:26px; font-weight:800; color:inherit;">₹ {fastest.total_cost_inr:,.0f}</div>
                <p style="font-size:13px; color:inherit; opacity:0.75; margin:2px 0 12px 0;">Immediate Velocity Recovery</p>
                <div style="border-top:1px solid rgba(128, 128, 128, 0.2); padding-top:10px; font-size:13px; color:inherit;">
                    <p style="margin:4px 0; color:inherit;">⏱️ <b>Added Delay:</b> +{fastest.total_delay_hours:.1f} hrs {mitigated_tag}</p>
                    <p style="margin:4px 0; color:inherit;">🛡️ <b>Reliability:</b> {fastest.reliability_score * 100:.0f}%</p>
                    <p style="margin:4px 0; color:inherit;">🚛 <b>Truck:</b> Backup Fleet ({fastest.carrier_slot_id})</p>
                    <p style="margin:4px 0; color:inherit;">🏬 <b>Dock:</b> Expedited Bay ({fastest.warehouse_slot_id})</p>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        if st.button("Select Fastest Plan", key="btn_fastest", use_container_width=True, type="secondary" if not is_sel else "primary"):
            st.session_state["selected_plan_category"] = PlanCategory.FASTEST.value
            st.session_state["selected_plan"] = fastest
            st.session_state["force_regenerate_explanation"] = True
            st.rerun()

    # Card 3: Safest Plan
    with col3:
        is_sel = selected_category == PlanCategory.SAFEST.value
        border = "#f59e0b" if is_sel else "rgba(128, 128, 128, 0.25)"
        bg = "rgba(245, 158, 11, 0.12)" if is_sel else "rgba(128, 128, 128, 0.08)"
        st.markdown(
            f"""
            <div style="background:{bg}; border:2px solid {border}; border-radius:12px; padding:16px; margin-bottom:12px; box-shadow:0 4px 6px -1px rgba(0,0,0,0.05);">
                <span style="background:rgba(245, 158, 11, 0.18); color:#f59e0b; border:1px solid rgba(245, 158, 11, 0.35); font-size:11px; font-weight:700; padding:3px 8px; border-radius:12px;">RECOMMENDED</span>
                <h3 style="margin:8px 0 4px 0; color:#f59e0b;">🛡️ Safest Plan</h3>
                <div style="font-size:26px; font-weight:800; color:inherit;">₹ {safest.total_cost_inr:,.0f}</div>
                <p style="font-size:13px; color:inherit; opacity:0.75; margin:2px 0 12px 0;">Maximum On-Time Resilience</p>
                <div style="border-top:1px solid rgba(128, 128, 128, 0.2); padding-top:10px; font-size:13px; color:inherit;">
                    <p style="margin:4px 0; color:inherit;">⏱️ <b>Added Delay:</b> +{safest.total_delay_hours:.1f} hrs (Buffer Protected)</p>
                    <p style="margin:4px 0; color:inherit;">🛡️ <b>Reliability:</b> {safest.reliability_score * 100:.0f}% (Highest)</p>
                    <p style="margin:4px 0; color:inherit;">🚛 <b>Truck:</b> Protected Fleet ({safest.carrier_slot_id})</p>
                    <p style="margin:4px 0; color:inherit;">🏬 <b>Dock:</b> Reserved Bay ({safest.warehouse_slot_id})</p>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        if st.button("Select Safest Plan", key="btn_safest", use_container_width=True, type="secondary" if not is_sel else "primary"):
            st.session_state["selected_plan_category"] = PlanCategory.SAFEST.value
            st.session_state["selected_plan"] = safest
            st.session_state["force_regenerate_explanation"] = True
            st.rerun()
