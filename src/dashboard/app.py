"""FreightFlow AI - Modern Enterprise Streamlit Dashboard Entry Point."""

import sys
import os
from pathlib import Path

# Add project root to sys.path so 'src' and modules are discoverable
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
from src.dashboard.components.cascade_view import render_cascade_view
from src.dashboard.components.plan_comparator import render_plan_comparator
from src.dashboard.components.human_approval import render_human_approval
from src.dashboard.components.timeline_view import render_timeline_view
from src.dashboard.components.metrics_view import render_metrics_view
from src.common.config import GEMINI_API_KEY, GEMINI_MODEL, save_gemini_api_key
from src.llm.explainer import LLMExplainer

st.set_page_config(
    page_title="FreightFlow AI - Disruption Prediction & Recovery",
    page_icon="🚢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ──────────────────────────────────────────────────────────────────
# Modern Global CSS Injection
# ──────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* Global Container Adjustments with Top Header Clearance */
    .block-container {
        padding-top: 4.5rem !important; /* Ample breathing room below Streamlit navbar/header */
        padding-bottom: 2.5rem !important;
        max-width: 96% !important;
    }

    /* Hide distracting Deploy button if present */
    .stAppDeployButton {
        display: none !important;
    }
    
    /* Top Header Bar */
    .ff-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        border-radius: 12px;
        padding: 18px 24px;
        color: #f8fafc;
        margin-top: 0.5rem !important;
        margin-bottom: 22px !important;
        box-shadow: 0 4px 15px -2px rgba(0, 0, 0, 0.2);
    }
    
    .ff-title {
        font-size: 24px;
        font-weight: 800;
        margin: 0;
        color: #ffffff;
        letter-spacing: -0.5px;
    }
    
    .ff-subtitle {
        font-size: 13px;
        color: #94a3b8;
        margin: 4px 0 0 0;
    }

    .ff-badge-container {
        display: flex;
        gap: 10px;
        align-items: center;
        flex-wrap: wrap;
    }

    .ff-badge {
        background: rgba(255, 255, 255, 0.08);
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 20px;
        padding: 5px 12px;
        font-size: 12px;
        font-weight: 600;
        color: #e2e8f0;
    }

    .ff-badge-green {
        background: rgba(34, 197, 94, 0.15);
        border: 1px solid #22c55e;
        color: #4ade80;
    }

    .ff-badge-purple {
        background: rgba(168, 85, 247, 0.18);
        border: 1px solid #a855f7;
        color: #c084fc;
    }

    .ff-badge-amber {
        background: rgba(245, 158, 11, 0.15);
        border: 1px solid #f59e0b;
        color: #fbbf24;
    }

    /* ─────────────────────────────────────────────────────────────
       Modern Floating Separated Button Navigation Bar (Centered)
       ───────────────────────────────────────────────────────────── */
    [data-testid="stTabs"] > div:first-child {
        display: flex !important;
        justify-content: center !important;
        width: 100% !important;
    }

    [data-testid="stTabs"] [role="tablist"],
    [data-testid="stTabs"] [data-baseweb="tab-list"] {
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        gap: 20px !important;
        border-bottom: none !important;
        background: transparent !important;
        padding: 10px 4px 24px 4px !important;
        margin: 0 auto !important;
        width: 100% !important;
        overflow-x: auto;
    }

    [data-testid="stTabs"] [role="tab"] {
        border-radius: 9999px !important; /* Full pill shape */
        padding: 10px 22px !important;
        font-weight: 600 !important;
        font-size: 14px !important;
        border: 1px solid rgba(128, 128, 128, 0.22) !important;
        background: rgba(128, 128, 128, 0.08) !important;
        color: inherit !important;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.06) !important;
        transition: all 0.22s cubic-bezier(0.4, 0, 0.2, 1) !important;
        margin-right: 0px !important;
        outline: none !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
    }

    [data-testid="stTabs"] [role="tab"]:hover {
        border-color: rgba(56, 189, 248, 0.6) !important;
        background: rgba(56, 189, 248, 0.12) !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 12px rgba(56, 189, 248, 0.2) !important;
    }

    [data-testid="stTabs"] [role="tab"][aria-selected="true"] {
        background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%) !important;
        color: #ffffff !important;
        border-color: #38bdf8 !important;
        box-shadow: 0 4px 16px rgba(2, 132, 199, 0.45) !important;
        transform: translateY(-1px) !important;
    }

    [data-testid="stTabs"] [role="tab"][aria-selected="true"] p,
    [data-testid="stTabs"] [role="tab"][aria-selected="true"] div {
        color: #ffffff !important;
        font-weight: 700 !important;
    }

    /* Text color inside inactive tab */
    [data-testid="stTabs"] [role="tab"][aria-selected="false"] p,
    [data-testid="stTabs"] [role="tab"][aria-selected="false"] div {
        color: inherit !important;
        opacity: 0.9 !important;
    }

    /* Completely remove the attached underline indicator */
    .react-aria-SelectionIndicator,
    [data-testid="stTabs"] .react-aria-SelectionIndicator,
    [data-testid="stTabs"] [data-baseweb="tab-highlight"],
    [data-testid="stTabs"] hr {
        display: none !important;
        height: 0px !important;
        opacity: 0 !important;
        border: none !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)


def render_sidebar():
    """Renders comprehensive Gemini API and operational configuration in the sidebar."""
    with st.sidebar:
        st.markdown("### 🤖 Google Gemini AI Engine")
        st.caption("Empower autonomous recovery plans with Google Generative AI trade-off analysis.")

        # Ensure session keys initialized
        if "gemini_api_key" not in st.session_state:
            st.session_state["gemini_api_key"] = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or GEMINI_API_KEY or ""
        if "gemini_model" not in st.session_state or st.session_state.get("gemini_model") in ("gemini-2.5-flash", "gemini-3.8-flash"):
            st.session_state["gemini_model"] = os.getenv("GEMINI_MODEL") or "gemini-3.5-flash"

        current_key = st.session_state["gemini_api_key"]
        has_key = bool(current_key and current_key not in ("your_gemini_api_key_here", "AIzaSy..."))

        # Visual Status Pill
        if has_key:
            masked = current_key[:6] + "..." + current_key[-4:] if len(current_key) > 12 else "***"
            st.success(f"🟢 **Live Gemini API Connected**\n\nKey: `{masked}`")
        else:
            st.warning("🟡 **Offline Rule Engine Active**\n\n(No Gemini key configured. Running high-fidelity offline heuristic fallback.)")

        # API Key Input
        input_key = st.text_input(
            "Gemini API Key",
            value=current_key,
            type="password",
            placeholder="AIzaSy...",
            help="Get a free Gemini API key from Google AI Studio (https://aistudio.google.com/app/apikey)"
        )

        # Model Selector
        model_options = ["gemini-3.5-flash", "gemini-3.7-flash", "gemini-3.8-flash", "gemini-flash-latest"]
        current_idx = model_options.index(st.session_state["gemini_model"]) if st.session_state["gemini_model"] in model_options else 0
        selected_model = st.selectbox("Gemini Model", model_options, index=current_idx)

        # Action Buttons
        col_test, col_save = st.columns(2)
        with col_test:
            if st.button("⚡ Test Key", use_container_width=True):
                if input_key.strip():
                    with st.spinner("Connecting to Google Gemini..."):
                        explainer = LLMExplainer(api_key=input_key.strip(), model=selected_model)
                        success, msg = explainer.test_connection()
                        if success:
                            st.success(msg)
                        else:
                            st.error(msg)
                else:
                    st.error("Please enter an API key first.")

        with col_save:
            if st.button("💾 Save Key", use_container_width=True, type="primary"):
                clean_key = input_key.strip()
                st.session_state["gemini_api_key"] = clean_key
                st.session_state["gemini_model"] = selected_model
                save_gemini_api_key(clean_key, selected_model)
                st.session_state["force_regenerate_explanation"] = True
                st.success("Configuration saved and persisted!")
                st.rerun()

        st.markdown("---")
        st.markdown("#### ℹ️ Hackathon Guidance")
        st.markdown(
            """
            * **Get a Free Key:** [Google AI Studio](https://aistudio.google.com/app/apikey)
            * **Zero-Setup Resilience:** If no key is set, FreightFlow AI continues to run with 100% full fidelity using its built-in deterministic heuristic trade-off engine.
            """
        )
        st.markdown("---")
        st.caption("FreightFlow AI v2.4 • Team VisionWeavers")


def render_top_header():
    """Renders sleek top SaaS header bar with branding and live status."""
    current_key = st.session_state.get("gemini_api_key", "")
    has_gemini = bool(current_key and current_key not in ("your_gemini_api_key_here", "AIzaSy..."))
    
    if has_gemini:
        model_name = st.session_state.get("gemini_model", "gemini-2.5-flash")
        gemini_badge = f'<span class="ff-badge ff-badge-purple">✨ Gemini Active ({model_name})</span>'
    else:
        gemini_badge = '<span class="ff-badge ff-badge-amber">🤖 Heuristic AI Engine</span>'

    st.markdown(
        f"""
        <div class="ff-header">
            <div>
                <div class="ff-title">🚢 FreightFlow AI: Disruption Prediction & Recovery</div>
                <div class="ff-subtitle">Cross-Party Autonomous Logistics Coordination Powered by Multi-Agent Negotiation</div>
            </div>
            <div class="ff-badge-container">
                <span class="ff-badge ff-badge-green">🟢 Gateway Active</span>
                {gemini_badge}
                <span class="ff-badge">Team VisionWeavers</span>
                <span class="ff-badge">1,200 Telemetry Consignments</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_pitch_architecture():
    """Renders clean visual architecture summary for judge Q&A."""
    st.markdown("#### 🏛️ System Architecture & Workflow Walkthrough")
    st.caption("How FreightFlow AI transforms supply chain disruption handling from reactive alerts to autonomous negotiation:")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            """
            ##### 1. Problem: The Cascade Today
            * **Siloed Systems:** Seaports, trucking fleets, and warehouses operate without shared real-time coordination.
            * **Domino Failures:** A 4-hour port delay cascades into:
              * Driver waiting idle at the gate (₹500/hr detention).
              * Forfeited warehouse dock intake slot (₹12,500 penalty).
              * Warehouse overtime labor wages (₹1,800/hr).
              * Customer contractual SLA penalty (₹3,000/hr).
            * **Total Baseline Damage:** ₹17,750+ for a single shipment (`SHP-1005`).
            """
        )
    with col2:
        st.markdown(
            """
            ##### 2. The FreightFlow AI Solution
            * **1. Proactive Risk Prediction:** Scikit-learn GradientBoosting flags delays before compounding.
            * **2. 4-Node Cascade Graph:** NetworkX DAG maps downstream nodes and calculates exact ₹ at risk.
            * **3. 3-Round Multi-Agent Negotiation:**
              * **Port Agent:** Evaluates delayed berths vs. expedited priority cranes.
              * **Carrier Agent:** Evaluates driver wait vs. backup fleet dispatch.
              * **Warehouse Agent:** Evaluates evening overtime vs. next-morning 08:00 AM slot.
            * **4. Pareto-Ranked Plans:** Central Coordinator outputs **Cheapest**, **Fastest**, and **Safest** options.
            * **5. Human-in-the-Loop & Gemini:** Plain-English LLM trade-off explanation and interactive supervisor Q&A.
            """
        )


def main():
    # 1. Render Modern Sidebar with Gemini Config
    render_sidebar()

    # 2. Render Top Branded Header
    render_top_header()

    # 3. Modern Top Navigation Bar (Centered 3 Tabs)
    tab1, tab2, tab3 = st.tabs([
        "📡 1. Live Operations & Cascade Impact",
        "🤝 2. Multi-Agent Recovery & Approval",
        "📈 3. Simulation Benchmarks (50 Runs)"
    ])

    with tab1:
        render_cascade_view()

    with tab2:
        render_plan_comparator()
        st.divider()
        render_human_approval()
        st.divider()
        render_timeline_view()

    with tab3:
        render_metrics_view()


if __name__ == "__main__":
    main()
