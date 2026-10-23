"""Side-by-side comparison of Top 3 recovery plans (Cheapest, Fastest, Safest)."""

import streamlit as st
from src.agents.coordinator import CentralCoordinator
from src.cascade.impact_analyzer import compute_cascade_impact
from src.common.schemas import PlanCategory


def render_plan_comparator():
    """Renders trade-off comparison between Cheapest, Fastest, and Safest plans."""
    impact = st.session_state.get("current_impact")
    if not impact:
        # Default to SHP-1005 4h delay if user navigates directly here
        impact = compute_cascade_impact("SHP-1005", added_delay_hours=4.0)
        st.session_state["current_impact"] = impact
        st.session_state["current_shipment_id"] = "SHP-1005"

    coordinator = CentralCoordinator()
    plans = coordinator.run_recovery_negotiation(impact)
    st.session_state["negotiated_plans"] = plans

    st.markdown("### 2. Multi-Agent Negotiation Outcomes")
    st.caption("Central Coordinator orchestrated 3 rounds across Port, Carrier, and Warehouse agents, producing 3 non-dominated Pareto plans:")

    col1, col2, col3 = st.columns(3)
    
    # Plans map
    cheapest = next((p for p in plans if p.category == PlanCategory.CHEAPEST), plans[0])
    fastest = next((p for p in plans if p.category == PlanCategory.FASTEST), plans[1] if len(plans) > 1 else plans[0])
    safest = next((p for p in plans if p.category == PlanCategory.SAFEST), plans[2] if len(plans) > 2 else plans[0])

    selected = st.session_state.get("selected_plan_category", PlanCategory.SAFEST.value)

    with col1:
        st.success("🟢 **Cheapest Plan**")
        st.write(f"**Total Cost:** ₹ {cheapest.total_cost_inr:,.2f}")
        st.write(f"**Added Delay:** +{cheapest.total_delay_hours:.1f} hrs")
        st.write(f"**Reliability:** {cheapest.reliability_score * 100:.0f}%")
        st.caption("Driver waits; standard shift dock bay.")
        if st.button("Select Cheapest Plan", key="btn_cheapest", use_container_width=True):
            st.session_state["selected_plan_category"] = PlanCategory.CHEAPEST.value
            st.session_state["selected_plan"] = cheapest
            st.rerun()

    with col2:
        st.info("⚡ **Fastest Plan**")
        st.write(f"**Total Cost:** ₹ {fastest.total_cost_inr:,.2f}")
        st.write(f"**Added Delay:** +{fastest.total_delay_hours:.1f} hrs")
        st.write(f"**Reliability:** {fastest.reliability_score * 100:.0f}%")
        st.caption("Priority crane offloading; backup truck.")
        if st.button("Select Fastest Plan", key="btn_fastest", use_container_width=True):
            st.session_state["selected_plan_category"] = PlanCategory.FASTEST.value
            st.session_state["selected_plan"] = fastest
            st.rerun()

    with col3:
        st.warning("🛡️ **Safest Plan (Recommended)**")
        st.write(f"**Total Cost:** ₹ {safest.total_cost_inr:,.2f}")
        st.write(f"**Added Delay:** +{safest.total_delay_hours:.1f} hrs")
        st.write(f"**Reliability:** {safest.reliability_score * 100:.0f}%")
        st.caption("Buffered window; confirmed dock bay reservation.")
        if st.button("Select Safest Plan", key="btn_safest", use_container_width=True):
            st.session_state["selected_plan_category"] = PlanCategory.SAFEST.value
            st.session_state["selected_plan"] = safest
            st.rerun()

    # Set default selected plan if not already set
    if "selected_plan" not in st.session_state:
        st.session_state["selected_plan"] = safest
        st.session_state["selected_plan_category"] = PlanCategory.SAFEST.value

    st.info(f"Currently active selection: **{st.session_state['selected_plan_category']} Plan**")
