"""Central Coordinator orchestrating multi-agent negotiation rounds and ranking recovery plans."""

from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
from src.common.schemas import (
    DisruptionEvent,
    DisruptionType,
    RecoveryPlan,
    PlanCategory,
    CascadeImpact,
    AgentOffer,
)
from src.agents.carrier_agent import CarrierAgent
from src.agents.port_agent import PortAgent
from src.agents.warehouse_agent import WarehouseAgent


def is_pareto_dominated(candidate: RecoveryPlan, all_candidates: List[RecoveryPlan]) -> bool:
    """Evaluates whether candidate is Pareto-dominated by any other candidate.

    In FreightFlow AI, the multi-objective optimization problem is:
      - Minimize total_cost_inr (lower is better)
      - Minimize total_delay_hours (lower is better)
      - Maximize reliability_score (higher is better)

    Plan B dominates Plan A iff:
      B.cost <= A.cost AND B.delay <= A.delay AND B.rel >= A.rel
      AND at least one inequality is strict (< or >).
    """
    for other in all_candidates:
        if other is candidate:
            continue
        cost_better_or_equal = other.total_cost_inr <= candidate.total_cost_inr
        delay_better_or_equal = other.total_delay_hours <= candidate.total_delay_hours
        rel_better_or_equal = other.reliability_score >= candidate.reliability_score

        cost_strictly_better = other.total_cost_inr < candidate.total_cost_inr
        delay_strictly_better = other.total_delay_hours < candidate.total_delay_hours
        rel_strictly_better = other.reliability_score > candidate.reliability_score

        if (
            cost_better_or_equal
            and delay_better_or_equal
            and rel_better_or_equal
            and (cost_strictly_better or delay_strictly_better or rel_strictly_better)
        ):
            return True
    return False


def compute_pareto_frontier(candidates: List[RecoveryPlan]) -> List[RecoveryPlan]:
    """Returns the subset of non-dominated candidates (the Pareto frontier)."""
    return [c for c in candidates if not is_pareto_dominated(c, candidates)]


class CentralCoordinator:
    """Manages 3-round negotiation across carrier, port, and warehouse agents.

    Drives multi-party agreement from actual CascadeImpact information,
    gathers autonomous agent offers across 3 rounds with constraint updates,
    and derives the Top 3 plans (Cheapest, Fastest, Safest) verified by
    Pareto dominance calculations.
    """

    def __init__(self, max_rounds: int = 3):
        self.max_rounds = max(1, max_rounds)
        self.carrier_agent = CarrierAgent()
        self.port_agent = PortAgent()
        self.warehouse_agent = WarehouseAgent()

    # ──────────────────────────────────────────────────────────────────
    # Primary public interface
    # ──────────────────────────────────────────────────────────────────

    def run_recovery_negotiation(self, impact: CascadeImpact) -> List[RecoveryPlan]:
        """Runs the 3-round multi-agent negotiation driven by CascadeImpact.

        Args:
            impact: CascadeImpact object containing downstream delay propagation,
                    node details, and financial risk assessment.

        Returns:
            List of 3 RecoveryPlan objects: [Cheapest, Fastest, Safest].

        Raises:
            ValueError: If impact is missing or contains invalid negative delays.
        """
        if impact is None:
            raise ValueError(
                "CentralCoordinator.run_recovery_negotiation: 'impact' is required."
            )

        # 1. Extract delays from CascadeImpact
        delays = self._extract_delays(impact)
        ref_time = datetime.utcnow()
        event_id = impact.disruption_event_id or (
            f"EVT-{impact.shipment_id}" if impact.shipment_id else "EVT-RECOVERY"
        )

        # 2. Execute 3 Negotiation Rounds
        # Round 1: Autonomous baseline offers (individual cheaper preference)
        port_ctx_r1 = {"delay_hours": delays["port"], "reference_time": ref_time}
        carrier_ctx_r1 = {
            "delay_hours": delays["carrier"],
            "driver_rate_per_hr": 500.0,
            "reference_time": ref_time,
        }
        whs_ctx_r1 = {"delay_hours": delays["warehouse"], "reference_time": ref_time}

        offer_p1 = self.port_agent.generate_initial_offer(round_num=1, context=port_ctx_r1)
        offer_c1 = self.carrier_agent.generate_initial_offer(round_num=1, context=carrier_ctx_r1)
        offer_w1 = self.warehouse_agent.generate_initial_offer(round_num=1, context=whs_ctx_r1)

        # Round 2: Constraint-driven counteroffers (Speed and Reliability exploration)
        # Feedback signals coordinator preferences based on impact risk severity
        prefer_speed = impact.risk_level in ("HIGH", "CRITICAL") or delays["port"] >= 2.0

        port_fb_r2 = {
            "delay_hours": delays["port"],
            "prefer_cheap": not prefer_speed,
            "prefer_fast": prefer_speed,
            "reference_time": ref_time,
        }
        carrier_fb_r2 = {
            "delay_hours": delays["carrier"],
            "prefer_fast": prefer_speed,
            "reference_time": ref_time,
        }
        whs_fb_r2 = {
            "delay_hours": delays["warehouse"],
            "prefer_fast": prefer_speed,  # In speed mode, warehouse offers overtime
            "prefer_reliable": not prefer_speed,
            "reference_time": ref_time,
        }

        offer_p2 = self.port_agent.generate_counter_offer(round_num=2, coordinator_feedback=port_fb_r2)
        offer_c2 = self.carrier_agent.generate_counter_offer(round_num=2, coordinator_feedback=carrier_fb_r2)
        offer_w2 = self.warehouse_agent.generate_counter_offer(round_num=2, coordinator_feedback=whs_fb_r2)

        # Round 3: Cost-containment & Convergence counteroffers (Best and Final Offers)
        port_fb_r3 = {
            "delay_hours": delays["port"],
            "prefer_cheap": True,  # Test lower-cost deferred berth under cost ceiling
            "reference_time": ref_time,
        }
        carrier_fb_r3 = {
            "delay_hours": delays["carrier"],
            "prefer_fast": False,  # Evaluate cost-minimized driver wait
            "reference_time": ref_time,
        }
        whs_fb_r3 = {
            "delay_hours": delays["warehouse"],
            "prefer_reliable": True,  # Highest reliability morning slot
            "reference_time": ref_time,
        }

        offer_p3 = self.port_agent.generate_counter_offer(round_num=3, coordinator_feedback=port_fb_r3)
        offer_c3 = self.carrier_agent.generate_counter_offer(round_num=3, coordinator_feedback=carrier_fb_r3)
        offer_w3 = self.warehouse_agent.generate_counter_offer(round_num=3, coordinator_feedback=whs_fb_r3)

        # 3. Assemble Candidate Recovery Plans from Agent Options
        # Distinct options from the 3 agents:
        port_options = self._collect_distinct_options(
            [offer_p1, offer_p2, offer_p3],
            agent_role="PORT",
            delay_hrs=delays["port"],
        )
        carrier_options = self._collect_distinct_options(
            [offer_c1, offer_c2, offer_c3],
            agent_role="CARRIER",
            delay_hrs=delays["carrier"],
        )
        whs_options = self._collect_distinct_options(
            [offer_w1, offer_w2, offer_w3],
            agent_role="WAREHOUSE",
            delay_hrs=delays["warehouse"],
        )

        candidate_plans = self._build_candidate_plans(
            port_options=port_options,
            carrier_options=carrier_options,
            whs_options=whs_options,
            event_id=event_id,
            delays=delays,
        )

        # 4. Compute Pareto Frontier & Select Cheapest, Fastest, Safest
        pareto_plans = compute_pareto_frontier(candidate_plans)
        feasible_pool = [p for p in candidate_plans if p.is_feasible]
        if not feasible_pool:
            raise RuntimeError("No feasible recovery plan could be formed by agents.")

        # Select Cheapest: minimum total_cost_inr (tie-break: lower delay, higher rel)
        cheapest_plan = min(
            feasible_pool,
            key=lambda p: (p.total_cost_inr, p.total_delay_hours, -p.reliability_score),
        )
        # Select Fastest: minimum total_delay_hours (tie-break: lower cost, higher rel)
        fastest_plan = min(
            feasible_pool,
            key=lambda p: (p.total_delay_hours, p.total_cost_inr, -p.reliability_score),
        )
        # Select Safest: maximum reliability_score (tie-break: lower cost, lower delay)
        safest_plan = max(
            feasible_pool,
            key=lambda p: (p.reliability_score, -p.total_cost_inr, -p.total_delay_hours),
        )

        # Clone and tag categories
        plan_cheap = self._clone_plan_with_category(cheapest_plan, PlanCategory.CHEAPEST, event_id)
        plan_fast = self._clone_plan_with_category(fastest_plan, PlanCategory.FASTEST, event_id)
        plan_safe = self._clone_plan_with_category(safest_plan, PlanCategory.SAFEST, event_id)

        return [plan_cheap, plan_fast, plan_safe]

    # ──────────────────────────────────────────────────────────────────
    # Backward compatibility wrapper
    # ──────────────────────────────────────────────────────────────────

    def coordinate_recovery(
        self,
        disruption: DisruptionEvent,
        impact: Optional[CascadeImpact] = None,
    ) -> Tuple[List[RecoveryPlan], bool]:
        """Legacy interface wrapper for coordinate_recovery.

        Accepts either a disruption event (and optional impact) and returns
        (plans, is_feasible).
        """
        if impact is None:
            # Construct a synthesized CascadeImpact from the disruption event
            impact = CascadeImpact(
                disruption_event_id=disruption.event_id,
                shipment_id=disruption.source_entity_id if disruption.source_entity_id.startswith("SHP-") else None,
                initial_delay_hours=disruption.delay_hours,
                downstream_delay_hours=disruption.delay_hours,
                total_cascaded_delay_hours=disruption.delay_hours,
                risk_level="HIGH" if disruption.severity_level >= 0.7 else "MEDIUM" if disruption.severity_level >= 0.4 else "LOW",
            )
        plans = self.run_recovery_negotiation(impact)
        is_feasible = any(p.is_feasible for p in plans) if plans else False
        return plans, is_feasible

    # ──────────────────────────────────────────────────────────────────
    # Helper routines
    # ──────────────────────────────────────────────────────────────────

    def _extract_delays(self, impact: CascadeImpact) -> Dict[str, float]:
        """Extracts node delays from CascadeImpact or falls back to top-level delay."""
        base_delay = impact.initial_delay_hours if impact.initial_delay_hours > 0 else impact.downstream_delay_hours
        if base_delay < 0:
            raise ValueError(
                f"CentralCoordinator: impact delay must be >= 0, got {base_delay}"
            )

        port_delay = base_delay
        truck_delay = base_delay
        whs_delay = base_delay

        if impact.nodes:
            for node in impact.nodes:
                ntype = getattr(node, "node_type", "")
                ndelay = getattr(node, "delay_hours", 0.0)
                if ntype == "PORT":
                    port_delay = ndelay
                elif ntype == "TRUCK":
                    truck_delay = ndelay
                elif ntype == "WAREHOUSE":
                    whs_delay = ndelay

        return {
            "port": max(0.0, float(port_delay)),
            "carrier": max(0.0, float(truck_delay)),
            "warehouse": max(0.0, float(whs_delay)),
        }

    def _collect_distinct_options(
        self,
        offers: List[AgentOffer],
        agent_role: str,
        delay_hrs: float,
    ) -> List[Dict[str, Any]]:
        """Extracts unique operational options from multi-round agent offers."""
        seen_types = set()
        options = []

        for off in offers:
            slot_id = off.slot_id
            if agent_role == "PORT":
                is_expedited = "EXPEDITED" in slot_id
                key = "EXPEDITED" if is_expedited else "DELAYED"
                if key not in seen_types:
                    seen_types.add(key)
                    options.append({
                        "slot_id": slot_id,
                        "type": key,
                        "cost": off.cost_inr,
                        "reliability": off.reliability_score,
                        "added_delay": 0.0 if is_expedited else delay_hrs,
                        "constraints_met": off.constraints_met,
                    })
            elif agent_role == "CARRIER":
                is_replace = "REPLACEMENT" in slot_id
                key = "REPLACEMENT" if is_replace else "WAIT"
                if key not in seen_types:
                    seen_types.add(key)
                    options.append({
                        "slot_id": slot_id,
                        "type": key,
                        "cost": off.cost_inr,
                        "reliability": off.reliability_score,
                        "added_delay": 0.0 if is_replace else delay_hrs,
                        "constraints_met": off.constraints_met,
                    })
            elif agent_role == "WAREHOUSE":
                is_r3 = "R3" in slot_id
                is_morning = "MORNING" in slot_id
                key = "RESERVED" if is_r3 else ("MORNING" if is_morning else "OVERTIME")
                if key not in seen_types:
                    seen_types.add(key)
                    options.append({
                        "slot_id": slot_id,
                        "type": "MORNING" if (is_morning or is_r3) else "OVERTIME",
                        "cost": off.cost_inr + (600.0 if is_r3 else 0.0),
                        "reliability": min(0.99, off.reliability_score + (0.05 if is_r3 else 0.0)),
                        "added_delay": 14.0 if (is_morning or is_r3) else delay_hrs,
                        "constraints_met": off.constraints_met,
                    })

        # Supplement with agent alternatives if an option was not explored during rounds
        dummy_event = DisruptionEvent(
            event_id="EVT-ALT",
            event_type=DisruptionType.PORT_CONGESTION,
            source_entity_id="ENTITY",
            severity_level=0.5,
            delay_hours=delay_hrs,
            description="Alternative evaluation",
        )
        if agent_role == "PORT":
            for alt in self.port_agent.get_alternatives(dummy_event):
                is_exp = "EXPEDITED" in alt["slot_id"]
                key = "EXPEDITED" if is_exp else "DELAYED"
                if key not in seen_types:
                    seen_types.add(key)
                    options.append({
                        "slot_id": alt["slot_id"],
                        "type": key,
                        "cost": alt["cost_inr"],
                        "reliability": alt["reliability_score"],
                        "added_delay": 0.0 if is_exp else delay_hrs,
                        "constraints_met": True,
                    })
        elif agent_role == "CARRIER":
            for alt in self.carrier_agent.get_alternatives(dummy_event):
                is_rep = "REPLACEMENT" in alt["slot_id"]
                key = "REPLACEMENT" if is_rep else "WAIT"
                if key not in seen_types:
                    seen_types.add(key)
                    options.append({
                        "slot_id": alt["slot_id"],
                        "type": key,
                        "cost": alt["cost_inr"],
                        "reliability": alt["reliability_score"],
                        "added_delay": 0.0 if is_rep else delay_hrs,
                        "constraints_met": True,
                    })
        elif agent_role == "WAREHOUSE":
            for alt in self.warehouse_agent.get_alternatives(dummy_event):
                is_morn = "MORNING" in alt["slot_id"]
                key = "MORNING" if is_morn else "OVERTIME"
                if key not in seen_types:
                    seen_types.add(key)
                    options.append({
                        "slot_id": alt["slot_id"],
                        "type": key,
                        "cost": alt["cost_inr"],
                        "reliability": alt["reliability_score"],
                        "added_delay": 14.0 if is_morn else delay_hrs,
                        "constraints_met": True,
                    })

        return options

    def _build_candidate_plans(
        self,
        port_options: List[Dict[str, Any]],
        carrier_options: List[Dict[str, Any]],
        whs_options: List[Dict[str, Any]],
        event_id: str,
        delays: Dict[str, float],
    ) -> List[RecoveryPlan]:
        """Constructs all combinatorial candidate recovery plans across agents."""
        candidates = []
        plan_counter = 1

        for p in port_options:
            for c in carrier_options:
                for w in whs_options:
                    total_cost = round(p["cost"] + c["cost"] + w["cost"], 2)

                    # Delay propagation:
                    # Port offload delay propagates to carrier unless port is expedited
                    port_effective_delay = p["added_delay"]
                    # If carrier replaces truck, carrier wait delay is 0; otherwise waits for port
                    if c["type"] == "REPLACEMENT":
                        transit_delay = port_effective_delay
                    else:
                        transit_delay = max(port_effective_delay, c["added_delay"])

                    # If warehouse defers to next-morning slot, total delay is shifted by 14h
                    if w["type"] == "MORNING":
                        total_delay = max(transit_delay, 14.0)
                    else:
                        total_delay = transit_delay

                    total_delay = round(max(0.0, float(total_delay)), 2)

                    # Serial system reliability product
                    reliability = round(
                        p["reliability"] * c["reliability"] * w["reliability"], 3
                    )
                    is_feasible = (
                        p["constraints_met"]
                        and c["constraints_met"]
                        and w["constraints_met"]
                    )

                    candidate = RecoveryPlan(
                        plan_id=f"CANDIDATE-{plan_counter}-{event_id}",
                        category=PlanCategory.CHEAPEST,
                        carrier_slot_id=c["slot_id"],
                        port_slot_id=p["slot_id"],
                        warehouse_slot_id=w["slot_id"],
                        total_cost_inr=total_cost,
                        total_delay_hours=total_delay,
                        reliability_score=reliability,
                        cost_breakdown={
                            "port": p["cost"],
                            "carrier": c["cost"],
                            "warehouse": w["cost"],
                        },
                        negotiation_rounds_taken=3,
                        is_feasible=is_feasible,
                    )
                    candidates.append(candidate)
                    plan_counter += 1

        return candidates

    def _clone_plan_with_category(
        self,
        source_plan: RecoveryPlan,
        category: PlanCategory,
        event_id: str,
    ) -> RecoveryPlan:
        """Clones a candidate plan and assigns its official PlanCategory."""
        return RecoveryPlan(
            plan_id=f"PLAN-{category.value}-{event_id}",
            category=category,
            carrier_slot_id=source_plan.carrier_slot_id,
            port_slot_id=source_plan.port_slot_id,
            warehouse_slot_id=source_plan.warehouse_slot_id,
            total_cost_inr=source_plan.total_cost_inr,
            total_delay_hours=source_plan.total_delay_hours,
            reliability_score=source_plan.reliability_score,
            cost_breakdown=dict(source_plan.cost_breakdown),
            negotiation_rounds_taken=source_plan.negotiation_rounds_taken,
            is_feasible=source_plan.is_feasible,
            llm_explanation=None,
        )
