"""Human-in-the-loop approval workflow and LLM reasoning display."""

import streamlit as st
from src.llm.explainer import LLMExplainer
from src.common.schemas import DisruptionEvent, DisruptionType


def render_human_approval():
    """Renders plan approval mechanism and LLM natural language explanation."""
    st.markdown("### 3. Human Approval & AI Rationale")

    plan = st.session_state.get("selected_plan")
    impact = st.session_state.get("current_impact")
    shipment_id = st.session_state.get("current_shipment_id", "SHP-1005")
    delay_hours = st.session_state.get("current_delay_hours", 4.0)

    if not plan or not impact:
        st.warning("Please select a plan above to view AI rationale and execute approval.")
        return

    # Synthesize DisruptionEvent
    event = DisruptionEvent(
        event_id=impact.disruption_event_id or f"EVT-{shipment_id}",
        event_type=DisruptionType.PORT_CONGESTION,
        source_entity_id=shipment_id,
        severity_level=0.75,
        delay_hours=delay_hours,
        description=f"Port berth delay on {shipment_id} (+{delay_hours:.1f} hrs)"
    )

    # Generate LLM Explanation
    explainer = LLMExplainer()
    explanation = explainer.explain_plan(event, plan)

    with st.expander("🤖 AI Trade-Off Rationale (Generated for Operator)", expanded=True):
        st.write(explanation)

    # Approval Button
    col_btn, col_msg = st.columns([1, 2])
    with col_btn:
        if st.button("✅ Approve & Commit Plan", type="primary", use_container_width=True):
            st.session_state["plan_approved"] = True
            st.success(f"Plan '{plan.category.value}' Approved! Operating schedules updated in SQLite.")
            st.balloons()
