"""Shared milestone schedule and operating fees, consistent with geographic replay."""

from datetime import datetime, timedelta

import streamlit as st

from src.dashboard.components.map_simulation import build_replay_payload


def render_timeline_view():
    st.markdown("### 4. Schedule Realignment: Before vs. Disrupted vs. Recovery Preview")
    scenario = st.session_state.get("current_scenario")
    plan = st.session_state.get("selected_plan")
    if not scenario or not plan:
        st.info("Select a recovery plan to inspect its schedule.")
        return
    replay = build_replay_payload(scenario["bundle"], scenario["disruption_type"],
                                 scenario["delay_hours"], scenario=scenario)
    recovery = next(p for p in replay["plans"] if p["category"] == plan.category.value)
    origin = datetime.fromisoformat(scenario["bundle"]["shipment"]["eta_port_berth"]) - timedelta(hours=2)

    def clock(hours):
        return (origin + timedelta(hours=hours)).strftime("%d %b %H:%M")

    rows = []
    for label, key in [("Port berth", "berth"), ("Truck pickup", "pickup"),
                       ("Warehouse arrival", "arrival"), ("Customer delivery", "delivery")]:
        rows.append({"Milestone": label, "Nominal baseline": clock(replay["baseline"][key]),
                     "Unmitigated disruption": clock(replay["disrupted"][key]),
                     f"{plan.category.value} preview": clock(recovery["schedule"][key])})
    rows.insert(3, {"Milestone": "Warehouse intake", "Nominal baseline": clock(replay["slot"]),
                    "Unmitigated disruption": clock(max(replay["slot"], replay["disrupted"]["arrival"])),
                    f"{plan.category.value} preview": clock(recovery["schedule"]["intake"])})
    st.table(rows)
    st.caption(f"Customer contractual deadline: {clock(replay['promise'])}. Recovery milestone times use the same slot-action preview as the map; the coordinator's aggregate delay metric is separate.")
    st.dataframe([{"Agent": key.title(), "Recovery operating fee (₹)": value}
                  for key, value in plan.cost_breakdown.items()], hide_index=True, use_container_width=True)
    st.write(f"**Recovery operating fee: ₹{plan.total_cost_inr:,.2f}** · "
             f"Coordinator delay estimate: +{plan.total_delay_hours:.1f}h · "
             f"Modeled reliability: {plan.reliability_score:.0%}")
    st.caption("Operating fees exclude residual delivery penalties; they are not net savings or a guaranteed total landed cost.")
