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
        st.warning("Please select a recovery plan above to view AI rationale and execute approval.")
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
    model = st.session_state.get("gemini_model", "gemini-3.5-flash")
    explainer = LLMExplainer(api_key=api_key, model=model)

    # Detect if user selected a different plan category
    current_category = plan.category.value
    last_category = st.session_state.get("last_explained_category")
    if last_category != current_category:
        st.session_state["force_regenerate_explanation"] = True
        st.session_state["last_explained_category"] = current_category

    rationale_counter = st.session_state.get("rationale_counter", 0)
    exp_cache_key = f"explanation_{shipment_id}_{disruption_type_str}_{delay_hours:.1f}_{current_category}_{rationale_counter}"

    # Generate or retrieve cached explanation
    if exp_cache_key not in st.session_state or st.session_state.get("force_regenerate_explanation"):
        with st.spinner(f"Analyzing multi-agent trade-offs for {current_category} plan..."):
            explanation = explainer.explain_plan(event, plan, iteration=rationale_counter)
            st.session_state[exp_cache_key] = explanation
            st.session_state["active_explanation"] = explanation
            st.session_state["last_explainer_source"] = explainer.last_source
            st.session_state["last_explainer_model"] = explainer.last_model_used
            st.session_state["force_regenerate_explanation"] = False
    else:
        explanation = st.session_state.get("active_explanation") or st.session_state[exp_cache_key]

    source_used = st.session_state.get("last_explainer_source", explainer.last_source)
    model_used = st.session_state.get("last_explainer_model") or explainer.last_model_used or explainer.model
    if source_used == "gemini":
        source_badge = f"✨ **Powered by Google Gemini** (`{model_used}`)"
    else:
        source_badge = f"🤖 **Powered by FreightFlow Operational Rule Engine** (Perspective #{rationale_counter + 1})"

    with st.expander(f"🤖 AI Trade-Off Rationale for [{current_category}] Plan", expanded=True):
        st.caption(source_badge)
        st.markdown(explanation)

        # Interactive controls inside expander
        c_regen, c_pad = st.columns([1, 4])
        with c_regen:
            if st.button("🔄 Regenerate Rationale", key="btn_regen_rationale", use_container_width=True):
                st.session_state["rationale_counter"] = rationale_counter + 1
                st.session_state["force_regenerate_explanation"] = True
                st.rerun()

        # Custom interactive query section
        st.markdown("---")
        st.markdown("##### 💬 Ask Gemini AI about this Plan")
        with st.form(key=f"form_qa_{current_category}", clear_on_submit=False):
            user_query = st.text_input(
                f"Ask a question regarding the {current_category} recovery route:",
                placeholder="e.g. Which option to choose and why so? Or what about driver overtime?",
                key=f"q_{current_category}"
            )
            btn_submit = st.form_submit_button("Submit Question to AI")

        if btn_submit:
            if user_query and user_query.strip():
                with st.spinner("Consulting AI Operations Advisor..."):
                    negotiated_plans = st.session_state.get("negotiated_plans")
                    ai_answer = explainer.ask_custom_question(
                        event, plan, user_query.strip(), all_plans=negotiated_plans
                    )
                    st.session_state[f"last_custom_q_{current_category}"] = user_query.strip()
                    st.session_state[f"last_custom_answer_{current_category}"] = ai_answer
                    st.session_state[f"last_custom_source_{current_category}"] = explainer.last_source
                    st.session_state[f"last_custom_model_{current_category}"] = explainer.last_model_used or explainer.model
            else:
                st.warning("Please enter a question to consult Gemini.")

        # Persisted display of custom AI response
        saved_answer = st.session_state.get(f"last_custom_answer_{current_category}")
        saved_q = st.session_state.get(f"last_custom_q_{current_category}")
        saved_source = st.session_state.get(f"last_custom_source_{current_category}", "gemini")
        saved_model = st.session_state.get(f"last_custom_model_{current_category}", explainer.model)

        if saved_answer:
            badge_icon = "✨" if saved_source == "gemini" else "🤖"
            badge_text = f"Google Gemini (`{saved_model}`)" if saved_source == "gemini" else "FreightFlow Operational Advisory Engine"
            st.markdown(
                f"""
                <div style="background: rgba(30, 41, 59, 0.55); border: 1px solid rgba(56, 189, 248, 0.4); border-radius: 8px; padding: 12px 16px; margin: 14px 0 10px 0;">
                    <div style="font-size: 0.85rem; color: #94a3b8;">
                        {badge_icon} <strong>Advisory Response for:</strong> <em style="color: #f1f5f9;">"{saved_q}"</em> &nbsp;•&nbsp; 
                        <span style="color: #38bdf8; font-weight: 500;">{badge_text}</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
            st.markdown(saved_answer)

    # Approval and Commit Action
    col_btn, col_msg = st.columns([1, 2])
    with col_btn:
        if st.button("✅ Approve & Commit Plan", type="primary", use_container_width=True):
            st.session_state["plan_approved"] = True
            st.success(f"Plan '{plan.category.value}' Approved! Operating schedules updated in SQLite.")
            st.balloons()
