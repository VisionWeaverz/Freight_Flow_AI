"""Side-by-side comparison of Top 3 recovery plans (Cheapest, Fastest, Safest)."""

import streamlit as st
from src.agents.coordinator import CentralCoordinator
from src.cascade.impact_analyzer import compute_cascade_impact
from src.common.schemas import PlanCategory


def get_human_plan_attributes(plan, impact, cat: PlanCategory):
    """Translates raw operational codes and technical metrics into intuitive, human-understandable logistics terms."""
    # 1. Delivery Schedule
    if plan.total_delay_hours == 0.0:
        timing_badge = "ON TIME"
        timing_badge_bg = "rgba(34, 197, 94, 0.2)"
        timing_badge_color = "#22c55e"
        timing_title = "On-Time Delivery (0h Delay)"
        timing_desc = "⚡ Immediate priority turn-around fully clears initial delay"
    elif plan.total_delay_hours >= 12.0:
        timing_badge = "NEXT MORNING"
        timing_badge_bg = "rgba(245, 158, 11, 0.2)"
        timing_badge_color = "#f59e0b"
        timing_title = "Next-Day Morning (08:00 AM Slot)"
        timing_desc = f"🌙 Held overnight in secure depot; avoids costly night overtime wages (+{plan.total_delay_hours:.0f}h hold)"
    else:
        timing_badge = f"+{plan.total_delay_hours:.1f}H OFFSET"
        timing_badge_bg = "rgba(56, 189, 248, 0.2)"
        timing_badge_color = "#38bdf8"
        timing_title = f"+{plan.total_delay_hours:.1f}h Adjusted Arrival"
        timing_desc = "⏱️ Delivery offset absorbed within extended customer SLA grace buffer"

    # 2. Fleet & Road Transport Action
    c_slot = plan.carrier_slot_id or ""
    if "REPLACEMENT" in c_slot:
        truck_title = "Relief Replacement Fleet"
        truck_desc = f"Emergency backup carrier swaps in to bypass delay ({c_slot})"
    elif cat == PlanCategory.SAFEST:
        truck_title = "Protected Carrier with GPS Routing"
        truck_desc = f"Assigned high-compliance driver with dynamic route clearance ({c_slot})"
    else:
        truck_title = "Original Carrier Standby (No Swap)"
        truck_desc = f"Same driver waits on route; avoids ₹8,500 replacement fee ({c_slot})"

    # 3. Warehouse Dock Intake Action
    w_slot = plan.warehouse_slot_id or ""
    if "OVERTIME" in w_slot:
        dock_title = "Priority Overtime Bay (Evening Shift)"
        dock_desc = f"After-hours crew unloads cargo tonight without staging lag ({w_slot})"
    elif "R3" in w_slot or "RESERVED" in w_slot:
        dock_title = "Guaranteed Reserved Bay (08:00 AM)"
        dock_desc = f"Pre-booked bay with buffer; guarantees zero queue detention ({w_slot})"
    elif "MORNING" in w_slot:
        dock_title = "Next-Morning Intake Bay (08:00 AM)"
        dock_desc = f"Fresh day-shift crew handles intake; waives overtime fees ({w_slot})"
    else:
        dock_title = "Standard Assigned Intake Bay"
        dock_desc = f"Clears through standard warehouse gate reception ({w_slot})"

    # 4. Operational Execution Certainty
    rel_pct = plan.reliability_score * 100
    if rel_pct >= 85:
        rel_label = f"<b>{rel_pct:.0f}%</b> (High Certainty • Buffer Protected)"
    elif rel_pct >= 70:
        rel_label = f"<b>{rel_pct:.0f}%</b> (Good Certainty • Standard Shift)"
    else:
        rel_label = f"<b>{rel_pct:.0f}%</b> (Moderate Certainty • Tight Schedule)"

    # 5. Operational Net Strategy
    financial_risk = getattr(impact, "financial_risk_inr", 17750.0)
    savings = max(0, financial_risk - plan.total_cost_inr)
    if cat == PlanCategory.CHEAPEST:
        tradeoff = f"💡 <b>Strategy:</b> Holds cargo until standard morning shift to maximize cost savings (saves ₹{savings:,.0f} vs unmitigated fines)."
    elif cat == PlanCategory.FASTEST:
        tradeoff = "💡 <b>Strategy:</b> Deploys emergency priority resources to eliminate delay (0h lag) and protect customer delivery SLA."
    else:
        tradeoff = f"💡 <b>Strategy:</b> Balances low recovery cost with guaranteed reserved buffer slots for maximum schedule reliability."

    return {
        "timing_title": timing_title,
        "timing_desc": timing_desc,
        "timing_badge": timing_badge,
        "timing_badge_bg": timing_badge_bg,
        "timing_badge_color": timing_badge_color,
        "truck_title": truck_title,
        "truck_desc": truck_desc,
        "dock_title": dock_title,
        "dock_desc": dock_desc,
        "rel_label": rel_label,
        "tradeoff": tradeoff,
        "savings": savings,
    }


def render_plan_comparator():
    """Renders trade-off comparison between Cheapest, Fastest, and Safest plans."""
    impact = st.session_state.get("current_impact")
    if not impact:
        impact = compute_cascade_impact("SHP-1005", added_delay_hours=4.0)
        st.session_state["current_impact"] = impact
        st.session_state["current_shipment_id"] = "SHP-1005"

    coordinator = CentralCoordinator()
    plans = coordinator.run_recovery_negotiation(impact)
    st.session_state["negotiated_plans"] = plans

    # Active Disruption Context Pill linking Tab 1 to Tab 2
    shipment_id = st.session_state.get("current_shipment_id", "SHP-1005")
    disruption_type = st.session_state.get("current_disruption_type", "PORT_CONGESTION")
    delay_hours = getattr(impact, "initial_delay_hours", 4.0)
    risk_inr = getattr(impact, "financial_risk_inr", 17750.0)

    st.markdown(
        f"""
        <div style="background:rgba(2, 132, 199, 0.08); border:1.5px solid rgba(2, 132, 199, 0.3); border-radius:10px; padding:10px 16px; margin-bottom:14px; display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
            <div>
                <span style="font-size:11px; font-weight:700; color:#0284c7; text-transform:uppercase; letter-spacing:0.5px;">🎯 Active Target (from Tab 1):</span>
                <span style="font-size:14px; font-weight:800; margin-left:6px;">{shipment_id}</span>
                <span style="font-size:13px; opacity:0.85; margin-left:8px;">• {disruption_type.replace('_', ' ').title()} (+{delay_hours:.1f}h)</span>
            </div>
            <div>
                <span style="font-size:12px; opacity:0.8;">Baseline Unmitigated Damage:</span>
                <span style="font-size:14px; font-weight:800; color:#ef4444; margin-left:6px;">₹{risk_inr:,.0f}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("#### 🤝 Autonomous Multi-Agent Negotiation Outcomes")
    st.caption("The Central Coordinator resolved 3 rounds between Port, Carrier, and Warehouse agents, producing 3 non-dominated Pareto alternatives:")

    cheapest = next((p for p in plans if p.category == PlanCategory.CHEAPEST), plans[0])
    fastest = next((p for p in plans if p.category == PlanCategory.FASTEST), plans[1] if len(plans) > 1 else plans[0])
    safest = next((p for p in plans if p.category == PlanCategory.SAFEST), plans[2] if len(plans) > 2 else plans[0])

    plans_by_cat = {
        PlanCategory.CHEAPEST.value: cheapest,
        PlanCategory.FASTEST.value: fastest,
        PlanCategory.SAFEST.value: safest,
    }

    selected_category = st.session_state.get("selected_plan_category", PlanCategory.SAFEST.value)
    if selected_category not in plans_by_cat:
        selected_category = PlanCategory.SAFEST.value

    # Keep selected_plan synchronized with the active category on every render
    st.session_state["selected_plan_category"] = selected_category
    st.session_state["selected_plan"] = plans_by_cat[selected_category]

    info_cheap = get_human_plan_attributes(cheapest, impact, PlanCategory.CHEAPEST)
    info_fast = get_human_plan_attributes(fastest, impact, PlanCategory.FASTEST)
    info_safe = get_human_plan_attributes(safest, impact, PlanCategory.SAFEST)

    col1, col2, col3 = st.columns(3)

    # Card 1: Cheapest Plan
    with col1:
        is_sel = selected_category == PlanCategory.CHEAPEST.value
        border = "#22c55e" if is_sel else "rgba(128, 128, 128, 0.25)"
        bg = "rgba(34, 197, 94, 0.12)" if is_sel else "rgba(128, 128, 128, 0.08)"
        st.markdown(
            f"""
            <div style="background:{bg}; border:2px solid {border}; border-radius:12px; padding:16px; margin-bottom:12px; box-shadow:0 4px 6px -1px rgba(0,0,0,0.05);">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                    <span style="background:rgba(34, 197, 94, 0.18); color:#22c55e; border:1px solid rgba(34, 197, 94, 0.35); font-size:11px; font-weight:700; padding:3px 8px; border-radius:12px;">COST OPTIMIZED</span>
                    <span style="background:{info_cheap['timing_badge_bg']}; color:{info_cheap['timing_badge_color']}; font-size:10px; font-weight:800; padding:2px 7px; border-radius:8px;">{info_cheap['timing_badge']}</span>
                </div>
                <h3 style="margin:4px 0 2px 0; color:#22c55e; font-size:20px;">🟢 Cheapest Plan</h3>
                <div style="font-size:26px; font-weight:800; color:inherit;">₹ {cheapest.total_cost_inr:,.0f}</div>
                <p style="font-size:12px; color:#22c55e; font-weight:700; margin:2px 0 10px 0;">💰 Saves ₹{info_cheap['savings']:,.0f} vs. Disruption Damage</p>
                <div style="border-top:1px solid rgba(128, 128, 128, 0.2); padding-top:10px; font-size:12.5px; line-height:1.45;">
                    <div style="margin-bottom:8px;">
                        <span style="font-weight:700; color:inherit;">⏱️ Schedule:</span> <span style="font-weight:600; color:#38bdf8;">{info_cheap['timing_title']}</span>
                        <div style="font-size:11px; opacity:0.75; margin-top:1px;">{info_cheap['timing_desc']}</div>
                    </div>
                    <div style="margin-bottom:8px;">
                        <span style="font-weight:700; color:inherit;">🚛 Fleet:</span> <span style="font-weight:600; color:inherit;">{info_cheap['truck_title']}</span>
                        <div style="font-size:11px; opacity:0.75; margin-top:1px;">{info_cheap['truck_desc']}</div>
                    </div>
                    <div style="margin-bottom:8px;">
                        <span style="font-weight:700; color:inherit;">🏬 Dock:</span> <span style="font-weight:600; color:inherit;">{info_cheap['dock_title']}</span>
                        <div style="font-size:11px; opacity:0.75; margin-top:1px;">{info_cheap['dock_desc']}</div>
                    </div>
                    <div style="margin-bottom:9px;">
                        <span style="font-weight:700; color:inherit;">🛡️ Certainty:</span> {info_cheap['rel_label']}
                    </div>
                </div>
                <div style="background:rgba(128,128,128,0.08); border-radius:8px; padding:7px 9px; font-size:11.5px; opacity:0.9; margin-top:4px; border:1px solid rgba(128,128,128,0.15);">
                    {info_cheap['tradeoff']}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        if st.button("Select Cheapest Plan", key="btn_cheapest", use_container_width=True, type="secondary" if not is_sel else "primary"):
            st.session_state["selected_plan_category"] = PlanCategory.CHEAPEST.value
            st.session_state["selected_plan"] = cheapest
            st.session_state["force_regenerate_explanation"] = True
            st.rerun()

    # Card 2: Fastest Plan
    with col2:
        is_sel = selected_category == PlanCategory.FASTEST.value
        border = "#0ea5e9" if is_sel else "rgba(128, 128, 128, 0.25)"
        bg = "rgba(14, 165, 233, 0.12)" if is_sel else "rgba(128, 128, 128, 0.08)"
        st.markdown(
            f"""
            <div style="background:{bg}; border:2px solid {border}; border-radius:12px; padding:16px; margin-bottom:12px; box-shadow:0 4px 6px -1px rgba(0,0,0,0.05);">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                    <span style="background:rgba(14, 165, 233, 0.18); color:#0ea5e9; border:1px solid rgba(14, 165, 233, 0.35); font-size:11px; font-weight:700; padding:3px 8px; border-radius:12px;">SPEED PRIORITY</span>
                    <span style="background:{info_fast['timing_badge_bg']}; color:{info_fast['timing_badge_color']}; font-size:10px; font-weight:800; padding:2px 7px; border-radius:8px;">{info_fast['timing_badge']}</span>
                </div>
                <h3 style="margin:4px 0 2px 0; color:#0ea5e9; font-size:20px;">⚡ Fastest Plan</h3>
                <div style="font-size:26px; font-weight:800; color:inherit;">₹ {fastest.total_cost_inr:,.0f}</div>
                <p style="font-size:12px; color:#0ea5e9; font-weight:700; margin:2px 0 10px 0;">⚡ Immediate Velocity Recovery</p>
                <div style="border-top:1px solid rgba(128, 128, 128, 0.2); padding-top:10px; font-size:12.5px; line-height:1.45;">
                    <div style="margin-bottom:8px;">
                        <span style="font-weight:700; color:inherit;">⏱️ Schedule:</span> <span style="font-weight:600; color:#38bdf8;">{info_fast['timing_title']}</span>
                        <div style="font-size:11px; opacity:0.75; margin-top:1px;">{info_fast['timing_desc']}</div>
                    </div>
                    <div style="margin-bottom:8px;">
                        <span style="font-weight:700; color:inherit;">🚛 Fleet:</span> <span style="font-weight:600; color:inherit;">{info_fast['truck_title']}</span>
                        <div style="font-size:11px; opacity:0.75; margin-top:1px;">{info_fast['truck_desc']}</div>
                    </div>
                    <div style="margin-bottom:8px;">
                        <span style="font-weight:700; color:inherit;">🏬 Dock:</span> <span style="font-weight:600; color:inherit;">{info_fast['dock_title']}</span>
                        <div style="font-size:11px; opacity:0.75; margin-top:1px;">{info_fast['dock_desc']}</div>
                    </div>
                    <div style="margin-bottom:9px;">
                        <span style="font-weight:700; color:inherit;">🛡️ Certainty:</span> {info_fast['rel_label']}
                    </div>
                </div>
                <div style="background:rgba(128,128,128,0.08); border-radius:8px; padding:7px 9px; font-size:11.5px; opacity:0.9; margin-top:4px; border:1px solid rgba(128,128,128,0.15);">
                    {info_fast['tradeoff']}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        if st.button("Select Fastest Plan", key="btn_fastest", use_container_width=True, type="secondary" if not is_sel else "primary"):
            st.session_state["selected_plan_category"] = PlanCategory.FASTEST.value
            st.session_state["selected_plan"] = fastest
            st.session_state["force_regenerate_explanation"] = True
            st.rerun()

    # Card 3: Safest Plan
    with col3:
        is_sel = selected_category == PlanCategory.SAFEST.value
        border = "#f59e0b" if is_sel else "rgba(128, 128, 128, 0.25)"
        bg = "rgba(245, 158, 11, 0.12)" if is_sel else "rgba(128, 128, 128, 0.08)"
        st.markdown(
            f"""
            <div style="background:{bg}; border:2px solid {border}; border-radius:12px; padding:16px; margin-bottom:12px; box-shadow:0 4px 6px -1px rgba(0,0,0,0.05);">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                    <span style="background:rgba(245, 158, 11, 0.18); color:#f59e0b; border:1px solid rgba(245, 158, 11, 0.35); font-size:11px; font-weight:700; padding:3px 8px; border-radius:12px;">RECOMMENDED</span>
                    <span style="background:{info_safe['timing_badge_bg']}; color:{info_safe['timing_badge_color']}; font-size:10px; font-weight:800; padding:2px 7px; border-radius:8px;">{info_safe['timing_badge']}</span>
                </div>
                <h3 style="margin:4px 0 2px 0; color:#f59e0b; font-size:20px;">🛡️ Safest Plan</h3>
                <div style="font-size:26px; font-weight:800; color:inherit;">₹ {safest.total_cost_inr:,.0f}</div>
                <p style="font-size:12px; color:#f59e0b; font-weight:700; margin:2px 0 10px 0;">🛡️ Maximum On-Time Resilience</p>
                <div style="border-top:1px solid rgba(128, 128, 128, 0.2); padding-top:10px; font-size:12.5px; line-height:1.45;">
                    <div style="margin-bottom:8px;">
                        <span style="font-weight:700; color:inherit;">⏱️ Schedule:</span> <span style="font-weight:600; color:#38bdf8;">{info_safe['timing_title']}</span>
                        <div style="font-size:11px; opacity:0.75; margin-top:1px;">{info_safe['timing_desc']}</div>
                    </div>
                    <div style="margin-bottom:8px;">
                        <span style="font-weight:700; color:inherit;">🚛 Fleet:</span> <span style="font-weight:600; color:inherit;">{info_safe['truck_title']}</span>
                        <div style="font-size:11px; opacity:0.75; margin-top:1px;">{info_safe['truck_desc']}</div>
                    </div>
                    <div style="margin-bottom:8px;">
                        <span style="font-weight:700; color:inherit;">🏬 Dock:</span> <span style="font-weight:600; color:inherit;">{info_safe['dock_title']}</span>
                        <div style="font-size:11px; opacity:0.75; margin-top:1px;">{info_safe['dock_desc']}</div>
                    </div>
                    <div style="margin-bottom:9px;">
                        <span style="font-weight:700; color:inherit;">🛡️ Certainty:</span> {info_safe['rel_label']}
                    </div>
                </div>
                <div style="background:rgba(128,128,128,0.08); border-radius:8px; padding:7px 9px; font-size:11.5px; opacity:0.9; margin-top:4px; border:1px solid rgba(128,128,128,0.15);">
                    {info_safe['tradeoff']}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )
        if st.button("Select Safest Plan", key="btn_safest", use_container_width=True, type="secondary" if not is_sel else "primary"):
            st.session_state["selected_plan_category"] = PlanCategory.SAFEST.value
            st.session_state["selected_plan"] = safest
            st.session_state["force_regenerate_explanation"] = True
            st.rerun()
