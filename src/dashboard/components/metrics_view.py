"""Evaluation metrics and benchmark dashboard for 50-run simulation."""

import streamlit as st
from src.simulation.benchmark_runner import BenchmarkRunner


def render_metrics_view():
    """Visualizes 4 key benchmark metrics across 50 simulated runs."""
    st.markdown("### 50-Run Simulation Benchmark (Slide 6 Evaluation Plan)")
    st.caption("Empirical simulation comparing Baseline (Manual First-Come / Phone Coordination) vs. FreightFlow AI Autonomous Replanning.")

    col_btn, col_runs = st.columns([1, 2])
    with col_btn:
        runs_count = st.number_input("Number of Simulated Disruption Trials:", min_value=10, max_value=100, value=50, step=10)
        start_btn = st.button("▶ Run Simulation Benchmark Suite", type="primary")

    if start_btn or "benchmark_summary" in st.session_state:
        if start_btn:
            with st.spinner(f"Running {runs_count} stochastic disruption simulations..."):
                runner = BenchmarkRunner(runs=runs_count)
                summary = runner.run_benchmark()
                st.session_state["benchmark_summary"] = summary
        
        summary = st.session_state["benchmark_summary"]

        st.divider()
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Avg Delay Reduction", f"{summary['avg_delay_reduction_pct']}%", delta="vs. Manual Baseline")
        with col2:
            st.metric("Driver Waiting Saved", f"{summary['avg_truck_waiting_saved_hrs']} hrs", delta="Per Trip Idle Reduction")
        with col3:
            st.metric("Avg Cost Saved", f"₹ {summary['avg_cost_saved_inr']:,.2f}", delta="Per Disruption Saved")
        with col4:
            st.metric("Conflicts Resolved", f"{summary['conflicts_resolved_pct']}%", delta="Feasible Multi-Party Plans")

        st.markdown("#### Sample Disruption Runs Log")
        records = summary.get("records", [])[:15]
        st.dataframe(records, use_container_width=True)
    else:
        st.info("👆 Click **'Run Simulation Benchmark Suite'** above to execute the 50-run evaluation and view empirical results.")
