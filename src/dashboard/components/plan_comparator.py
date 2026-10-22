"""Side-by-side comparison of Top 3 recovery plans (Cheapest, Fastest, Safest)."""

import streamlit as st


def render_plan_comparator():
    """Renders trade-off comparison between Cheapest, Fastest, and Safest plans."""
    st.markdown("### Top 3 Negotiated Recovery Plans")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.success("🟢 **Cheapest Plan**")
        st.write("**Cost:** ₹ 9,200")
        st.write("**Delay:** +3.5 hrs")
        st.write("**Reliability:** 88%")
        st.button("Select Cheapest", key="btn_cheapest")

    with col2:
        st.info("⚡ **Fastest Plan**")
        st.write("**Cost:** ₹ 13,500")
        st.write("**Delay:** +1.2 hrs")
        st.write("**Reliability:** 91%")
        st.button("Select Fastest", key="btn_fastest")

    with col3:
        st.warning("🛡️ **Safest Plan**")
        st.write("**Cost:** ₹ 10,800")
        st.write("**Delay:** +2.0 hrs")
        st.write("**Reliability:** 98%")
        st.button("Select Safest", key="btn_safest")
