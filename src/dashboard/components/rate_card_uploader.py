"""Component for uploading custom pricing CSV rate cards and toggling between synthetic vs custom tariffs."""

import streamlit as st
from typing import Optional, Dict
from src.database.rate_manager import (
    get_active_pricing,
    is_custom_pricing_active,
    parse_pricing_csv,
    apply_pricing_to_db,
    reset_pricing_to_synthetic,
    get_sample_csv_template,
    SYNTHETIC_BASELINE_RATES,
    RATE_FIELD_METADATA,
)

SOURCE_OPTIONS = [
    "🔵 Synthetic Benchmark Rates",
    "🟢 Custom Uploaded CSV Rates"
]

DEFAULT_ENTERPRISE_RATES: Dict[str, float] = {
    "driver_waiting_cost_per_hr": 850.0,
    "sla_penalty_per_hour_inr": 5000.0,
    "missed_slot_penalty_inr": 20000.0,
    "overtime_cost_per_hr": 2500.0,
}


def _cb_on_tariff_radio_change(target_shipment_id: str):
    """Callback fired strictly when user clicks the radio button."""
    val = st.session_state.get("tariff_mode_selector", SOURCE_OPTIONS[0])
    if "Custom" in val:
        rates = st.session_state.get("custom_rates_cached")
        if not rates:
            st.session_state["tariff_mode_selector"] = SOURCE_OPTIONS[0]
            st.session_state["upload_error_msg"] = "Upload a CSV or load Demo Rates before selecting custom pricing."
            return
        success, msg = apply_pricing_to_db(rates, apply_to_all=True)
        if not success:
            st.session_state["tariff_mode_selector"] = SOURCE_OPTIONS[0]
            st.session_state["upload_error_msg"] = msg
            return
        st.session_state["pricing_source"] = "CUSTOM_CSV"
    else:
        success, msg = reset_pricing_to_synthetic(shipment_id=target_shipment_id, reset_all=True)
        if not success:
            st.session_state["tariff_mode_selector"] = SOURCE_OPTIONS[1]
            st.session_state["upload_error_msg"] = msg
            return
        st.session_state["pricing_source"] = "SYNTHETIC"
    _invalidate_cascade_cache()


def _cb_load_demo_rates():
    """Callback fired when Demo Rates button is clicked."""
    success, msg = apply_pricing_to_db(DEFAULT_ENTERPRISE_RATES, apply_to_all=True)
    if not success:
        st.session_state["upload_error_msg"] = msg
        return
    st.session_state["pricing_source"] = "CUSTOM_CSV"
    st.session_state["tariff_mode_selector"] = SOURCE_OPTIONS[1]
    st.session_state["custom_rates_cached"] = dict(DEFAULT_ENTERPRISE_RATES)
    st.session_state.pop("uploaded_file_name", None)
    _invalidate_cascade_cache()


def _cb_reset_defaults(target_shipment_id: str):
    """Callback fired when Reset Defaults button is clicked."""
    success, msg = reset_pricing_to_synthetic(shipment_id=target_shipment_id, reset_all=True)
    if not success:
        st.session_state["upload_error_msg"] = msg
        return
    st.session_state["pricing_source"] = "SYNTHETIC"
    st.session_state["tariff_mode_selector"] = SOURCE_OPTIONS[0]
    st.session_state["custom_rates_cached"] = None
    _invalidate_cascade_cache()


def _cb_on_csv_uploaded():
    """Callback fired immediately when a CSV file is uploaded."""
    uploaded = st.session_state.get("main_rate_card_file_uploader")
    if uploaded is not None:
        try:
            content = uploaded.getvalue().decode("utf-8", errors="replace")
            success, msg, parsed_rates = parse_pricing_csv(content)
            if success:
                success, msg = apply_pricing_to_db(parsed_rates, apply_to_all=True)
            if success:
                st.session_state["custom_rates_cached"] = parsed_rates
                st.session_state["uploaded_file_name"] = uploaded.name
                st.session_state["pricing_source"] = "CUSTOM_CSV"
                st.session_state["tariff_mode_selector"] = SOURCE_OPTIONS[1]
                _invalidate_cascade_cache()
            else:
                st.session_state["upload_error_msg"] = msg
        except Exception as e:
            st.session_state["upload_error_msg"] = str(e)


def render_rate_card_manager(
    target_shipment_id: str = "SHP-1005",
    show_header: bool = True
):
    """Renders the single interactive pricing source selector, CSV file uploader, and rate inspection card."""
    
    # Check if database currently has custom rates
    is_custom_in_db = is_custom_pricing_active(target_shipment_id)
    if "pricing_source" not in st.session_state:
        st.session_state["pricing_source"] = "CUSTOM_CSV" if is_custom_in_db else "SYNTHETIC"

    if "tariff_mode_selector" not in st.session_state:
        st.session_state["tariff_mode_selector"] = (
            SOURCE_OPTIONS[1] if st.session_state["pricing_source"] == "CUSTOM_CSV" else SOURCE_OPTIONS[0]
        )

    if show_header:
        st.markdown("#### 💰 Custom Pricing & Rate Card (CSV Upload)")
        st.caption("Upload a custom tariff CSV to override contract rates (driver detention, SLA fine, dock penalty, overtime wage), or use synthetic defaults.")

    col_mode, col_upload = st.columns([1.1, 1.4])

    with col_mode:
        st.radio(
            "Tariff Source Mode:",
            SOURCE_OPTIONS,
            key="tariff_mode_selector",
            on_change=_cb_on_tariff_radio_change,
            args=(target_shipment_id,)
        )

        col_btn1, col_btn2, col_btn3 = st.columns(3)
        with col_btn1:
            template_csv = get_sample_csv_template(format_type="key_value")
            st.download_button(
                label="📥 Template",
                data=template_csv,
                file_name="freightflow_rate_card_template.csv",
                mime="text/csv",
                use_container_width=True,
                key="main_dl_template_btn",
                help="Download sample CSV rate card template"
            )
        with col_btn2:
            st.button(
                "⚡ Demo Rates",
                use_container_width=True,
                key="main_load_demo_rates_btn",
                on_click=_cb_load_demo_rates,
                help="Instantly load enterprise rates (₹850/h driver, ₹5,000/h SLA)"
            )
        with col_btn3:
            st.button(
                "↺ Reset",
                use_container_width=True,
                key="main_reset_baseline_btn",
                on_click=_cb_reset_defaults,
                args=(target_shipment_id,),
                help="Restore synthetic benchmark baseline rates"
            )

    with col_upload:
        st.markdown("**📁 Upload Rate Card (.csv)**")
        st.file_uploader(
            "Upload Pricing CSV",
            type=["csv"],
            key="main_rate_card_file_uploader",
            on_change=_cb_on_csv_uploaded,
            help="Upload a CSV with rate columns: driver_waiting_cost_per_hr, sla_penalty_per_hour_inr, missed_slot_penalty_inr, overtime_cost_per_hr.",
            label_visibility="collapsed"
        )

        if "upload_error_msg" in st.session_state:
            st.error(f"⚠️ Upload Error: {st.session_state['upload_error_msg']}")
            del st.session_state["upload_error_msg"]

        if st.session_state.get("uploaded_file_name") and st.session_state["pricing_source"] == "CUSTOM_CSV":
            st.caption(f"Active Uploaded File: `{st.session_state['uploaded_file_name']}`")
        elif st.session_state["pricing_source"] == "CUSTOM_CSV":
            st.caption("Active: Enterprise custom tariffs loaded (you can replace anytime by uploading a CSV above).")

    # Active Tariff Rates Overview Table with explicit live HTML table
    active_rates = get_active_pricing(shipment_id=target_shipment_id)
    render_rates_summary_table(active_rates)


def render_rates_summary_table(active_rates: dict):
    """Renders a clean compact HTML table displaying baseline vs active pricing with live deltas."""
    is_custom = (
        st.session_state.get("pricing_source") == "CUSTOM_CSV" or
        is_custom_pricing_active()
    )
    
    table_rows = []
    for key, meta in RATE_FIELD_METADATA.items():
        baseline = float(meta["default"])
        current = float(active_rates.get(key, baseline))
        diff = current - baseline
        unit_suffix = meta["unit"].replace("₹ ", "").strip()
        
        if diff > 0:
            pct = (diff / baseline) * 100
            delta_html = f'<span style="background: rgba(34, 197, 94, 0.2); color: #4ade80; border: 1px solid rgba(34, 197, 94, 0.4); padding: 3px 10px; border-radius: 6px; font-weight: 700; font-size: 12px;">🔺 +₹{diff:,.2f} (+{pct:.0f}%)</span>'
            active_html = f'<span style="color: #4ade80; font-weight: 700; font-size: 14px;">₹ {current:,.2f} <span style="font-size: 11px; color: #94a3b8;">{unit_suffix}</span></span>'
        elif diff < 0:
            pct = (abs(diff) / baseline) * 100
            delta_html = f'<span style="background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4); padding: 3px 10px; border-radius: 6px; font-weight: 700; font-size: 12px;">🔻 -₹{abs(diff):,.2f} (-{pct:.0f}%)</span>'
            active_html = f'<span style="color: #f87171; font-weight: 700; font-size: 14px;">₹ {current:,.2f} <span style="font-size: 11px; color: #94a3b8;">{unit_suffix}</span></span>'
        else:
            delta_html = '<span style="background: rgba(148, 163, 184, 0.15); color: #94a3b8; border: 1px solid rgba(148, 163, 184, 0.25); padding: 3px 10px; border-radius: 6px; font-size: 12px; font-weight: 500;">0 (Benchmark Baseline)</span>'
            active_html = f'<span style="color: #f8fafc; font-weight: 600; font-size: 14px;">₹ {current:,.2f} <span style="font-size: 11px; color: #94a3b8;">{unit_suffix}</span></span>'

        table_rows.append(f"""
        <tr style="border-bottom: 1px solid rgba(255, 255, 255, 0.08);">
            <td style="padding: 10px 14px; color: #e2e8f0; font-weight: 600;">
                <div>{meta['label']}</div>
                <div style="font-size: 11px; color: #94a3b8; font-weight: 400; margin-top: 2px;">{meta['description']}</div>
            </td>
            <td style="padding: 10px 14px;">{active_html}</td>
            <td style="padding: 10px 14px; color: #94a3b8; font-size: 13px;">₹ {baseline:,.2f} <span style="font-size: 11px;">{unit_suffix}</span></td>
            <td style="padding: 10px 14px;">{delta_html}</td>
        </tr>
        """)

    table_html = f"""
    <div style="background: rgba(15, 23, 42, 0.65); border: 1px solid rgba(255, 255, 255, 0.12); border-radius: 8px; overflow: hidden; margin-top: 12px; margin-bottom: 10px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);">
        <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 13px;">
            <thead>
                <tr style="background: rgba(30, 41, 59, 0.85); border-bottom: 1px solid rgba(255, 255, 255, 0.15); color: #cbd5e1; text-transform: uppercase; font-size: 11px; letter-spacing: 0.5px;">
                    <th style="padding: 10px 14px;">Contract Tariff Parameter</th>
                    <th style="padding: 10px 14px;">Active Rate</th>
                    <th style="padding: 10px 14px;">Benchmark Default</th>
                    <th style="padding: 10px 14px;">Delta vs Benchmark</th>
                </tr>
            </thead>
            <tbody>
                {''.join(table_rows)}
            </tbody>
        </table>
    </div>
    """
    # Render HTML directly: Markdown treats blank lines and indented table rows
    # as code blocks, exposing the markup instead of displaying the rates.
    st.html(table_html)
    
    if is_custom:
        st.markdown(
            """
            <div style="background: rgba(34, 197, 94, 0.12); border-left: 4px solid #22c55e; padding: 8px 14px; border-radius: 4px; margin-top: 6px;">
                <span style="color: #4ade80; font-weight: 600;">🟢 Custom CSV Rates Active:</span>
                <span style="color: #cbd5e1; font-size: 13px;"> Total Financial ₹ at Risk and Multi-Agent Plan Costs are calculating with these custom tariffs.</span>
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            """
            <div style="background: rgba(59, 130, 246, 0.12); border-left: 4px solid #3b82f6; padding: 8px 14px; border-radius: 4px; margin-top: 6px;">
                <span style="color: #60a5fa; font-weight: 600;">🔵 Synthetic Baseline Active:</span>
                <span style="color: #cbd5e1; font-size: 13px;"> Standard benchmark rates are in effect. Upload a CSV or select custom mode to customize.</span>
            </div>
            """,
            unsafe_allow_html=True
        )


def render_sidebar_tariff_card():
    """Renders clean status overview in sidebar without competing widgets."""
    is_custom = (
        st.session_state.get("pricing_source") == "CUSTOM_CSV" or
        is_custom_pricing_active()
    )
    st.markdown("### 💰 Pricing & Tariffs")
    if is_custom:
        st.success("🟢 **Custom CSV Tariffs Active**\n\nFinancial risk and recovery trade-offs are evaluated using custom enterprise rates.")
        st.button(
            "↺ Reset Baseline Rates",
            use_container_width=True,
            key="sidebar_reset_btn",
            on_click=_cb_reset_defaults,
            args=("SHP-1005",)
        )
    else:
        st.info("🔵 **Synthetic Baseline Active**\n\nStandard benchmark rates (Driver: ₹500/h, SLA: ₹3,000/h). Use Tab 1 to upload custom CSV rate cards.")


def _invalidate_cascade_cache():
    """Forces Tab 1 and Tab 2 to re-evaluate with the updated pricing."""
    for key in ["cascade_inputs", "current_impact", "negotiated_plans", "selected_plan"]:
        if key in st.session_state:
            del st.session_state[key]
    st.session_state["force_regenerate_explanation"] = True
