"""FreightFlow AI - Modern Enterprise Streamlit Dashboard Entry Point."""

import sys
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

st.set_page_config(
    page_title="FreightFlow AI - Disruption Prediction & Recovery",
    page_icon="🚢",
    layout="wide",
    initial_sidebar_state="collapsed"
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

    /* ─────────────────────────────────────────────────────────────
       Modern Floating Separated Button Navigation Bar (Streamlit 1.66)
       ───────────────────────────────────────────────────────────── */
    [data-testid="stTabs"] [role="tablist"] {
        display: flex !important;
        gap: 16px !important;
        border-bottom: none !important;
        background: transparent !important;
        padding: 8px 4px 20px 4px !important;
        margin-bottom: 12px !important;
        border: none !important;
    }

    /* Individual Floating Button Island */
    [data-testid="stTabs"] [role="tab"],
    [data-testid="stTab"] {
        height: 48px !important;
        background: var(--secondary-background-color, #ffffff) !important;
        border: 1.5px solid rgba(128, 128, 128, 0.25) !important;
        border-radius: 50px !important; /* Full pill shape */
        padding: 0 24px !important;
        font-weight: 600 !important;
        font-size: 0.95rem !important;
        color: var(--text-color, #334155) !important;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.08), 0 1px 3px rgba(0, 0, 0, 0.05) !important;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        cursor: pointer !important;
        margin: 0 !important;
    }

    /* Floating Hover Lift Effect */
    [data-testid="stTabs"] [role="tab"]:hover,
    [data-testid="stTab"]:hover {
        transform: translateY(-3px) !important;
        box-shadow: 0 8px 22px rgba(0, 0, 0, 0.16) !important;
        border-color: #0284c7 !important;
        color: #0284c7 !important;
    }

    /* Active Selected Floating Pill with Gradient & Glow */
    [data-testid="stTabs"] [role="tab"][aria-selected="true"],
    [data-testid="stTabs"] [role="tab"][data-selected="true"],
    [data-testid="stTab"][aria-selected="true"] {
        background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%) !important;
        color: #ffffff !important;
        border: 1.5px solid #0284c7 !important;
        box-shadow: 0 8px 24px rgba(2, 132, 199, 0.45), 0 3px 8px rgba(2, 132, 199, 0.25) !important;
        transform: translateY(-3px) !important;
    }

    /* Text color inside active tab */
    [data-testid="stTabs"] [role="tab"][aria-selected="true"] p,
    [data-testid="stTabs"] [role="tab"][aria-selected="true"] div,
    [data-testid="stTabs"] [role="tab"][data-selected="true"] p {
        color: #ffffff !important;
        font-weight: 700 !important;
    }

    /* Text color inside inactive tab */
    [data-testid="stTabs"] [role="tab"][aria-selected="false"] p,
    [data-testid="stTabs"] [role="tab"][aria-selected="false"] div {
        color: var(--text-color, #334155) !important;
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


def render_top_header():
    """Renders sleek top SaaS header bar with branding and live status."""
    st.markdown(
        """
        <div class="ff-header">
            <div>
                <div class="ff-title">🚢 FreightFlow AI: Disruption Prediction & Recovery</div>
                <div class="ff-subtitle">Cross-Party Autonomous Logistics Coordination Powered by Multi-Agent Negotiation</div>
            </div>
            <div class="ff-badge-container">
                <span class="ff-badge ff-badge-green">🟢 Gateway Active</span>
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
            * **5. Human-in-the-Loop:** Plain-English LLM trade-off explanation and one-click execution.
            """
        )


def main():
    # 1. Render Top Branded Header
    render_top_header()

    # 2. Modern Top Navigation Bar (Tabs)
    tab1, tab2, tab3, tab4 = st.tabs([
        "📡 1. Live Operations & Cascade Impact",
        "🤝 2. Multi-Agent Recovery & Approval",
        "📈 3. Simulation Benchmarks (50 Runs)",
        "ℹ️ 4. System Architecture & Pitch"
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

    with tab4:
        render_pitch_architecture()


if __name__ == "__main__":
    main()
