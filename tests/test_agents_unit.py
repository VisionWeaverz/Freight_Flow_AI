"""Focused unit tests for PortAgent, CarrierAgent, and WarehouseAgent.

Tests cover:
  - Both alternative cost calculations with known inputs
  - generate_initial_offer: cheapest option chosen correctly
  - generate_counter_offer: responds to coordinator preference signals
  - get_alternatives: structure and ordering
  - Edge cases: zero delay, very long delay, negative delay (ValueError)
  - Invalid calculate_internal_cost inputs (missing keys, bad option)
"""

import pytest
from datetime import datetime, timedelta
from src.common.schemas import DisruptionEvent, DisruptionType, AgentRole, AgentOffer
from src.agents.port_agent import (
    PortAgent,
    EXPEDITED_HANDLING_RATE_PER_HR,
    ALTERNATIVE_SLOT_EXTRA_DELAY_HRS,
    BASE_BERTH_FEE_INR,
    DEFERRED_RELIABILITY,
    EXPEDITED_RELIABILITY,
)
from src.agents.carrier_agent import (
    CarrierAgent,
    REPLACEMENT_TRUCK_FLAT_COST_INR,
    REPLACEMENT_TRUCK_WAIT_HOURS,
    WAITING_RELIABILITY,
    REPLACEMENT_RELIABILITY,
)
from src.agents.warehouse_agent import (
    WarehouseAgent,
    EVENING_OVERTIME_RATE_PER_HR,
    NEXT_MORNING_HOLDING_FEE_INR,
    NEXT_MORNING_OVERTIME_HRS,
    OVERTIME_RELIABILITY,
    NEXT_MORNING_RELIABILITY,
)


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────

@pytest.fixture
def disruption_4hr():
    return DisruptionEvent(
        event_id="EVT-TEST-001",
        event_type=DisruptionType.PORT_CONGESTION,
        source_entity_id="SHP-1005",
        severity_level=0.75,
        delay_hours=4.0,
        description="4-hour port delay test",
    )


@pytest.fixture
def disruption_0hr():
    return DisruptionEvent(
        event_id="EVT-TEST-002",
        event_type=DisruptionType.PORT_CONGESTION,
        source_entity_id="SHP-1005",
        severity_level=0.1,
        delay_hours=0.0,
        description="Zero-delay on-time scenario",
    )


@pytest.fixture
def disruption_2hr():
    return DisruptionEvent(
        event_id="EVT-TEST-003",
        event_type=DisruptionType.TRAFFIC_INCIDENT,
        source_entity_id="SHP-2001",
        severity_level=0.4,
        delay_hours=2.0,
        description="2-hour traffic delay",
    )


REF_TIME = datetime(2026, 10, 23, 8, 0, 0)  # Fixed reference for deterministic timing


# ═════════════════════════════════════════════════════════════════════
# PORT AGENT TESTS
# ═════════════════════════════════════════════════════════════════════

class TestPortAgentCostCalculation:
    """calculate_internal_cost() — pure arithmetic, no side effects."""

    def setup_method(self):
        self.agent = PortAgent()

    def test_no_expediting_zero_delay(self):
        cost = self.agent.calculate_internal_cost({"delay_hours": 0.0, "expedited": False})
        assert cost == BASE_BERTH_FEE_INR

    def test_no_expediting_four_hour_delay(self):
        # Only the base fee — no expediting
        cost = self.agent.calculate_internal_cost({"delay_hours": 4.0, "expedited": False})
        assert cost == BASE_BERTH_FEE_INR

    def test_expedited_four_hour_delay(self):
        # base + 1500 × 4
        expected = BASE_BERTH_FEE_INR + EXPEDITED_HANDLING_RATE_PER_HR * 4.0
        cost = self.agent.calculate_internal_cost({"delay_hours": 4.0, "expedited": True})
        assert cost == expected

    def test_expedited_default_is_false(self):
        # If 'expedited' key is absent, defaults to non-expedited
        cost = self.agent.calculate_internal_cost({"delay_hours": 3.0})
        assert cost == BASE_BERTH_FEE_INR

    def test_missing_delay_hours_raises(self):
        with pytest.raises(ValueError, match="delay_hours"):
            self.agent.calculate_internal_cost({"expedited": True})

    def test_negative_delay_raises(self):
        with pytest.raises(ValueError, match="delay_hours"):
            self.agent.calculate_internal_cost({"delay_hours": -1.0})


class TestPortAgentAlternatives:
    """get_alternatives() — two options, correct costs and ordering."""

    def setup_method(self):
        self.agent = PortAgent()

    def test_returns_two_alternatives(self, disruption_4hr):
        alts = self.agent.get_alternatives(disruption_4hr)
        assert len(alts) == 2

    def test_option_a_is_delayed_slot(self, disruption_4hr):
        alts = self.agent.get_alternatives(disruption_4hr)
        a = alts[0]
        assert a["option"] == "A"
        assert a["slot_id"] == "BERTH-DELAYED"
        assert a["added_delay_hours"] == 4.0
        assert a["cost_inr"] == BASE_BERTH_FEE_INR
        assert a["reliability_score"] == DEFERRED_RELIABILITY

    def test_option_b_is_expedited_slot(self, disruption_4hr):
        alts = self.agent.get_alternatives(disruption_4hr)
        b = alts[1]
        assert b["option"] == "B"
        assert b["slot_id"] == "BERTH-EXPEDITED"
        assert b["added_delay_hours"] == 4.0 + ALTERNATIVE_SLOT_EXTRA_DELAY_HRS
        expected_cost = BASE_BERTH_FEE_INR + EXPEDITED_HANDLING_RATE_PER_HR * 4.0
        assert b["cost_inr"] == expected_cost
        assert b["reliability_score"] == EXPEDITED_RELIABILITY

    def test_zero_delay_option_b_cost(self, disruption_0hr):
        alts = self.agent.get_alternatives(disruption_0hr)
        # Expedited with 0 delay = just base fee
        assert alts[1]["cost_inr"] == BASE_BERTH_FEE_INR
        assert alts[1]["added_delay_hours"] == ALTERNATIVE_SLOT_EXTRA_DELAY_HRS


class TestPortAgentOffers:
    """generate_initial_offer / generate_counter_offer."""

    def setup_method(self):
        self.agent = PortAgent()
        self.ctx = {"delay_hours": 4.0, "reference_time": REF_TIME}

    def test_initial_offer_returns_agentOffer(self):
        offer = self.agent.generate_initial_offer(1, self.ctx)
        assert isinstance(offer, AgentOffer)
        assert offer.agent_role == AgentRole.PORT
        assert offer.round_number == 1

    def test_initial_offer_is_delayed_slot(self):
        offer = self.agent.generate_initial_offer(1, self.ctx)
        assert "DELAYED" in offer.slot_id
        assert offer.cost_inr == BASE_BERTH_FEE_INR

    def test_initial_offer_timing(self):
        offer = self.agent.generate_initial_offer(1, self.ctx)
        expected_start = REF_TIME + timedelta(hours=4.0)
        assert offer.proposed_start_time == expected_start

    def test_counter_offer_prefers_cheap_returns_delayed(self):
        fb = {"delay_hours": 4.0, "prefer_cheap": True, "reference_time": REF_TIME}
        offer = self.agent.generate_counter_offer(2, fb)
        assert "DELAYED" in offer.slot_id

    def test_counter_offer_expedited_when_not_prefer_cheap(self):
        fb = {"delay_hours": 4.0, "prefer_cheap": False, "reference_time": REF_TIME}
        offer = self.agent.generate_counter_offer(2, fb)
        assert "EXPEDITED" in offer.slot_id
        expected_cost = BASE_BERTH_FEE_INR + EXPEDITED_HANDLING_RATE_PER_HR * 4.0
        assert offer.cost_inr == expected_cost

    def test_negative_delay_raises(self):
        with pytest.raises(ValueError):
            self.agent.generate_initial_offer(1, {"delay_hours": -2.0})

    def test_evaluate_disruption_structure(self, disruption_4hr):
        result = self.agent.evaluate_disruption(disruption_4hr)
        assert "alternatives" in result
        assert result["delay_hours"] == 4.0
        assert len(result["alternatives"]) == 2

    def test_evaluate_disruption_negative_raises(self):
        with pytest.raises(ValueError):
            bad = DisruptionEvent(
                event_id="X", event_type=DisruptionType.PORT_CONGESTION,
                source_entity_id="X", severity_level=0.5,
                delay_hours=-1.0, description="bad"
            )
            self.agent.evaluate_disruption(bad)


# ═════════════════════════════════════════════════════════════════════
# CARRIER AGENT TESTS
# ═════════════════════════════════════════════════════════════════════

class TestCarrierAgentCostCalculation:
    """calculate_internal_cost() — pure arithmetic."""

    def setup_method(self):
        self.agent = CarrierAgent()

    def test_wait_option_zero_delay(self):
        cost = self.agent.calculate_internal_cost(
            {"option": "wait", "delay_hours": 0.0}
        )
        assert cost == 0.0

    def test_wait_option_three_hours_default_rate(self):
        # default rate 500 × 3 = 1500
        cost = self.agent.calculate_internal_cost(
            {"option": "wait", "delay_hours": 3.0}
        )
        assert cost == 1500.0

    def test_wait_option_custom_rate(self):
        cost = self.agent.calculate_internal_cost(
            {"option": "wait", "delay_hours": 4.0, "driver_rate_per_hr": 600.0}
        )
        assert cost == 2400.0

    def test_replace_option_flat_regardless_of_delay(self):
        for d in (0.0, 1.0, 4.0, 10.0):
            cost = self.agent.calculate_internal_cost(
                {"option": "replace", "delay_hours": d}
            )
            assert cost == REPLACEMENT_TRUCK_FLAT_COST_INR

    def test_missing_option_raises(self):
        with pytest.raises(ValueError, match="option"):
            self.agent.calculate_internal_cost({"delay_hours": 2.0})

    def test_invalid_option_raises(self):
        with pytest.raises(ValueError, match="option"):
            self.agent.calculate_internal_cost({"option": "fly", "delay_hours": 2.0})

    def test_missing_delay_hours_raises(self):
        with pytest.raises(ValueError, match="delay_hours"):
            self.agent.calculate_internal_cost({"option": "wait"})

    def test_negative_delay_raises(self):
        with pytest.raises(ValueError, match="delay_hours"):
            self.agent.calculate_internal_cost({"option": "wait", "delay_hours": -1.0})


class TestCarrierAgentAlternatives:
    """get_alternatives() — two options, break-even logic."""

    def setup_method(self):
        self.agent = CarrierAgent()

    def test_returns_two_alternatives(self, disruption_4hr):
        alts = self.agent.get_alternatives(disruption_4hr)
        assert len(alts) == 2

    def test_option_a_wait(self, disruption_4hr):
        alts = self.agent.get_alternatives(disruption_4hr)
        a = alts[0]
        assert a["option"] == "A"
        assert a["slot_id"] == "TRUCK-WAIT"
        assert a["wait_hours"] == 4.0
        # 500 × 4 = 2000
        assert a["cost_inr"] == 2000.0
        assert a["reliability_score"] == WAITING_RELIABILITY

    def test_option_b_replacement(self, disruption_4hr):
        alts = self.agent.get_alternatives(disruption_4hr)
        b = alts[1]
        assert b["option"] == "B"
        assert b["slot_id"] == "TRUCK-REPLACEMENT"
        assert b["wait_hours"] == REPLACEMENT_TRUCK_WAIT_HOURS
        assert b["cost_inr"] == REPLACEMENT_TRUCK_FLAT_COST_INR
        assert b["reliability_score"] == REPLACEMENT_RELIABILITY

    def test_zero_delay_wait_cost_is_zero(self, disruption_0hr):
        alts = self.agent.get_alternatives(disruption_0hr)
        assert alts[0]["cost_inr"] == 0.0

    def test_custom_driver_rate(self, disruption_4hr):
        alts = self.agent.get_alternatives(disruption_4hr, driver_rate_per_hr=600.0)
        # 600 × 4 = 2400
        assert alts[0]["cost_inr"] == 2400.0


class TestCarrierAgentOffers:
    """generate_initial_offer selects cheapest option."""

    def setup_method(self):
        self.agent = CarrierAgent()

    def test_initial_offer_returns_agentOffer(self, disruption_4hr):
        ctx = {"delay_hours": 4.0, "reference_time": REF_TIME}
        offer = self.agent.generate_initial_offer(1, ctx)
        assert isinstance(offer, AgentOffer)
        assert offer.agent_role == AgentRole.CARRIER

    def test_initial_offer_picks_cheaper_option_wait(self):
        # 500 × 2 = 1000 < 4500 → wait is cheaper
        ctx = {"delay_hours": 2.0, "driver_rate_per_hr": 500.0, "reference_time": REF_TIME}
        offer = self.agent.generate_initial_offer(1, ctx)
        assert offer.cost_inr == 1000.0
        assert "WAIT" in offer.slot_id

    def test_initial_offer_picks_cheaper_option_replace(self):
        # 500 × 10 = 5000 > 4500 → replacement is cheaper
        ctx = {"delay_hours": 10.0, "driver_rate_per_hr": 500.0, "reference_time": REF_TIME}
        offer = self.agent.generate_initial_offer(1, ctx)
        assert offer.cost_inr == REPLACEMENT_TRUCK_FLAT_COST_INR
        assert "REPLACEMENT" in offer.slot_id

    def test_initial_offer_breakeven_prefers_replacement(self):
        # 500 × 9 = 4500 = replacement → replacement preferred (no fatigue)
        ctx = {"delay_hours": 9.0, "driver_rate_per_hr": 500.0, "reference_time": REF_TIME}
        offer = self.agent.generate_initial_offer(1, ctx)
        assert "REPLACEMENT" in offer.slot_id

    def test_counter_offer_prefer_fast_gives_replacement(self):
        fb = {"delay_hours": 2.0, "prefer_fast": True, "reference_time": REF_TIME}
        offer = self.agent.generate_counter_offer(2, fb)
        assert "REPLACEMENT" in offer.slot_id
        assert offer.cost_inr == REPLACEMENT_TRUCK_FLAT_COST_INR

    def test_evaluate_disruption_structure(self, disruption_4hr):
        result = self.agent.evaluate_disruption(disruption_4hr)
        assert "alternatives" in result
        assert result["wait_hours"] == 4.0
        assert len(result["alternatives"]) == 2

    def test_negative_delay_raises(self):
        with pytest.raises(ValueError):
            self.agent.generate_initial_offer(1, {"delay_hours": -3.0})


# ═════════════════════════════════════════════════════════════════════
# WAREHOUSE AGENT TESTS
# ═════════════════════════════════════════════════════════════════════

class TestWarehouseAgentCostCalculation:
    """calculate_internal_cost() — pure arithmetic."""

    def setup_method(self):
        self.agent = WarehouseAgent()

    def test_overtime_zero_delay_is_zero(self):
        cost = self.agent.calculate_internal_cost(
            {"option": "overtime", "delay_hours": 0.0}
        )
        assert cost == 0.0

    def test_overtime_two_hours(self):
        cost = self.agent.calculate_internal_cost(
            {"option": "overtime", "delay_hours": 2.0}
        )
        assert cost == EVENING_OVERTIME_RATE_PER_HR * 2.0

    def test_overtime_four_hours(self):
        cost = self.agent.calculate_internal_cost(
            {"option": "overtime", "delay_hours": 4.0}
        )
        assert cost == EVENING_OVERTIME_RATE_PER_HR * 4.0

    def test_morning_flat_regardless_of_delay(self):
        for d in (0.0, 1.0, 4.0, 10.0):
            cost = self.agent.calculate_internal_cost(
                {"option": "morning", "delay_hours": d}
            )
            assert cost == NEXT_MORNING_HOLDING_FEE_INR

    def test_missing_option_raises(self):
        with pytest.raises(ValueError, match="option"):
            self.agent.calculate_internal_cost({"delay_hours": 2.0})

    def test_invalid_option_raises(self):
        with pytest.raises(ValueError, match="option"):
            self.agent.calculate_internal_cost({"option": "teleport", "delay_hours": 2.0})

    def test_missing_delay_hours_raises(self):
        with pytest.raises(ValueError, match="delay_hours"):
            self.agent.calculate_internal_cost({"option": "overtime"})

    def test_negative_delay_raises(self):
        with pytest.raises(ValueError, match="delay_hours"):
            self.agent.calculate_internal_cost({"option": "overtime", "delay_hours": -1.0})


class TestWarehouseAgentAlternatives:
    """get_alternatives() — breakeven at 2 hours overtime."""

    def setup_method(self):
        self.agent = WarehouseAgent()

    def test_returns_two_alternatives(self, disruption_4hr):
        alts = self.agent.get_alternatives(disruption_4hr)
        assert len(alts) == 2

    def test_option_a_overtime(self, disruption_4hr):
        alts = self.agent.get_alternatives(disruption_4hr)
        a = alts[0]
        assert a["option"] == "A"
        assert a["slot_id"] == "DOCK-OVERTIME"
        assert a["overtime_hours"] == 4.0
        # 1500 × 4 = 6000
        assert a["cost_inr"] == 6000.0
        assert a["reliability_score"] == OVERTIME_RELIABILITY

    def test_option_b_morning(self, disruption_4hr):
        alts = self.agent.get_alternatives(disruption_4hr)
        b = alts[1]
        assert b["option"] == "B"
        assert b["slot_id"] == "DOCK-MORNING"
        assert b["overtime_hours"] == NEXT_MORNING_OVERTIME_HRS
        assert b["cost_inr"] == NEXT_MORNING_HOLDING_FEE_INR
        assert b["reliability_score"] == NEXT_MORNING_RELIABILITY

    def test_breakeven_at_two_hours(self, disruption_2hr):
        # 1500 × 2 = 3000 = morning fee → both equal; overtime is Option A
        alts = self.agent.get_alternatives(disruption_2hr)
        assert alts[0]["cost_inr"] == alts[1]["cost_inr"] == NEXT_MORNING_HOLDING_FEE_INR

    def test_zero_delay_overtime_is_zero(self, disruption_0hr):
        alts = self.agent.get_alternatives(disruption_0hr)
        assert alts[0]["cost_inr"] == 0.0
        assert alts[1]["cost_inr"] == NEXT_MORNING_HOLDING_FEE_INR


class TestWarehouseAgentOffers:
    """generate_initial_offer selects cheapest; counter_offer respects preference."""

    def setup_method(self):
        self.agent = WarehouseAgent()

    def test_initial_offer_returns_agentOffer(self, disruption_4hr):
        ctx = {"delay_hours": 4.0, "reference_time": REF_TIME}
        offer = self.agent.generate_initial_offer(1, ctx)
        assert isinstance(offer, AgentOffer)
        assert offer.agent_role == AgentRole.WAREHOUSE

    def test_initial_offer_prefers_overtime_when_cheaper(self, disruption_2hr):
        # 1500 × 1 = 1500 < 3000 → overtime cheaper
        ctx = {"delay_hours": 1.0, "reference_time": REF_TIME}
        offer = self.agent.generate_initial_offer(1, ctx)
        assert "OVERTIME" in offer.slot_id
        assert offer.cost_inr == 1500.0

    def test_initial_offer_prefers_morning_when_cheaper(self):
        # 1500 × 3 = 4500 > 3000 → morning cheaper
        ctx = {"delay_hours": 3.0, "reference_time": REF_TIME}
        offer = self.agent.generate_initial_offer(1, ctx)
        assert "MORNING" in offer.slot_id
        assert offer.cost_inr == NEXT_MORNING_HOLDING_FEE_INR

    def test_initial_offer_overtime_breakeven(self):
        # 1500 × 2 = 3000 = morning → overtime preferred (less delay)
        ctx = {"delay_hours": 2.0, "reference_time": REF_TIME}
        offer = self.agent.generate_initial_offer(1, ctx)
        assert "OVERTIME" in offer.slot_id

    def test_counter_offer_prefer_reliable_gives_morning(self, disruption_2hr):
        fb = {"delay_hours": 2.0, "prefer_reliable": True, "reference_time": REF_TIME}
        offer = self.agent.generate_counter_offer(2, fb)
        assert "MORNING" in offer.slot_id
        assert offer.reliability_score == NEXT_MORNING_RELIABILITY

    def test_morning_offer_timing(self):
        from src.agents.warehouse_agent import compute_next_morning_slot
        ctx = {"delay_hours": 5.0, "reference_time": REF_TIME}
        offer = self.agent.generate_initial_offer(1, ctx)
        # 5 hours overtime > morning → morning selected
        expected_start = compute_next_morning_slot(REF_TIME)
        assert offer.proposed_start_time == expected_start
        assert offer.proposed_start_time == datetime(2026, 10, 24, 8, 0, 0)

    @pytest.mark.parametrize(
        "request_time,expected_slot",
        [
            (datetime(2026, 10, 23, 9, 0, 0), datetime(2026, 10, 24, 8, 0, 0)),   # Morning 09:00
            (datetime(2026, 10, 23, 18, 0, 0), datetime(2026, 10, 24, 8, 0, 0)),  # Evening 18:00
            (datetime(2026, 10, 23, 23, 30, 0), datetime(2026, 10, 24, 8, 0, 0)), # Late-night 23:30
        ],
    )
    def test_next_morning_slot_calendar_aware(self, request_time, expected_slot):
        from src.agents.warehouse_agent import compute_next_morning_slot
        assert compute_next_morning_slot(request_time) == expected_slot
        # Verify via agent offer
        offer = self.agent.generate_initial_offer(
            1, {"delay_hours": 5.0, "reference_time": request_time}
        )
        assert offer.proposed_start_time == expected_slot
        assert offer.proposed_end_time == expected_slot + timedelta(hours=3)

    def test_next_morning_slot_timezone_aware(self):
        from datetime import timezone
        from src.agents.warehouse_agent import compute_next_morning_slot
        req_tz = datetime(2026, 10, 23, 18, 0, 0, tzinfo=timezone.utc)
        expected_tz = datetime(2026, 10, 24, 8, 0, 0, tzinfo=timezone.utc)
        computed = compute_next_morning_slot(req_tz)
        assert computed == expected_tz
        assert computed.tzinfo == timezone.utc

    def test_evaluate_disruption_structure(self, disruption_4hr):
        result = self.agent.evaluate_disruption(disruption_4hr)
        assert "alternatives" in result
        assert result["delay_hours"] == 4.0
        assert len(result["alternatives"]) == 2

    def test_negative_delay_raises(self):
        with pytest.raises(ValueError):
            self.agent.generate_initial_offer(1, {"delay_hours": -1.0})
