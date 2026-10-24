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
    disruption_type_str = st.session_state.get("current_disruption_type", "PORT_CONGESTION")

    if not plan or not impact:
        st.warning("Please select a plan above to view AI rationale and execute approval.")
        return

    # Parse DisruptionType enum safely
    try:
        event_type = DisruptionType(disruption_type_str)
    except Exception:
        event_type = DisruptionType.PORT_CONGESTION

    # Synthesize DisruptionEvent matching active UI state
    event_desc_map = {
        "PORT_CONGESTION": f"Port berth congestion on {shipment_id} (+{delay_hours:.1f} hrs)",
        "VESSEL_DELAY": f"Vessel arrival delay on {shipment_id} (+{delay_hours:.1f} hrs)",
        "TRUCK_BREAKDOWN": f"Carrier truck mechanical breakdown on {shipment_id} (+{delay_hours:.1f} hrs)",
        "TRAFFIC_INCIDENT": f"Expressway highway congestion on {shipment_id} (+{delay_hours:.1f} hrs)",
        "WAREHOUSE_BOTTLENECK": f"Destination warehouse dock intake stall on {shipment_id} (+{delay_hours:.1f} hrs)",
    }
    desc = event_desc_map.get(disruption_type_str, f"Disruption on {shipment_id} (+{delay_hours:.1f} hrs)")

    event = DisruptionEvent(
        event_id=impact.disruption_event_id or f"EVT-{shipment_id}",
        event_type=event_type,
        source_entity_id=shipment_id,
        severity_level=min(1.0, delay_hours / 6.0),
        delay_hours=delay_hours,
        description=desc
    )

    # Initialize LLM Explainer with active session configuration
    api_key = st.session_state.get("gemini_api_key")
    model = st.session_state.get("gemini_model", "gemini-3.8-flash")
    explainer = LLMExplainer(api_key=api_key, model=model)

    # Cache explanation in session state per plan category to avoid repetitive API latency
    exp_cache_key = f"explanation_{shipment_id}_{disruption_type_str}_{delay_hours:.1f}_{plan.category.value}_{bool(explainer.is_configured())}"
    
    if exp_cache_key not in st.session_state or st.session_state.get("force_regenerate_explanation"):
        explanation = explainer.explain_plan(event, plan)
        st.session_state[exp_cache_key] = explanation
        st.session_state["last_explainer_source"] = explainer.last_source
        st.session_state["last_explainer_model"] = explainer.last_model_used
        st.session_state["force_regenerate_explanation"] = False
    else:
        explanation = st.session_state[exp_cache_key]

    source_badge = (
        f"✨ Powered by Google Gemini (`{explainer.model}`)"
        if explainer.is_configured()
        else "🤖 Powered by FreightFlow Offline Rule Engine (Heuristic)"
    )

    with st.expander("🤖 AI Trade-Off Rationale (Generated for Operator)", expanded=True):
        st.caption(source_badge)
        st.markdown(explanation)

        # Interactive controls inside expander
        c_regen, c_pad = st.columns([1, 4])
        with c_regen:
            if st.button("🔄 Regenerate Rationale", use_container_width=True):
                st.session_state["force_regenerate_explanation"] = True
                st.rerun()

        # Custom interactive query section
        st.markdown("---")
        st.markdown("##### 💬 Ask Gemini AI about this Plan")
        user_query = st.text_input(
            "Operator question (e.g., 'What are the main risks with carrier backup fleet?')",
            placeholder="Type your question about costs, penalties, or driver constraints...",
            key=f"q_{plan.category.value}"
        )
        if st.button("Submit Question to AI", key=f"btn_q_{plan.category.value}"):
            if user_query.strip():
                with st.spinner("Consulting Gemini AI..."):
                    ai_answer = explainer.ask_custom_question(event, plan, user_query.strip())
                    st.info(ai_answer)
            else:
                st.warning("Please enter a question to consult Gemini.")

    # Approval and Commit Action
    col_btn, col_msg = st.columns([1, 2])
    with col_btn:
        if st.button("✅ Approve & Commit Plan", type="primary", use_container_width=True):
            st.session_state["plan_approved"] = True
            st.success(f"Plan '{plan.category.value}' Approved! Operating schedules updated in SQLite.")
            st.balloons()
