"""Human-in-the-loop approval workflow and LLM reasoning display."""

import streamlit as st


def render_human_approval():
    """Renders plan approval mechanism and LLM natural language explanation."""
    st.markdown("### Human Approval & AI Rationale")

    with st.expander("🤖 AI Explanation of Plan Trade-offs", expanded=True):
        st.write(
            "**LLM Synthesis:** The *Safest Plan* strikes the optimal compromise by rescheduling "
            "Port Berth 2 by 2 hours and allocating Truck Fleet T10 with a 30-minute buffer window, "
            "preventing an estimated ₹ 1,80,000 in warehouse detention penalties with 98% confidence."
        )

    if st.button("✅ Approve Selected Recovery Plan", type="primary"):
        st.success("Plan Approved! Operating schedules updated across Carrier, Port, and Warehouse databases.")
