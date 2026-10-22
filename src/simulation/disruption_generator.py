"""Synthetic disruption generator for port ETA shifts, traffic jams, and breakdowns."""

import random
from typing import List
from src.common.schemas import DisruptionEvent, DisruptionType


class DisruptionGenerator:
    """Generates stochastic disruption events for testing and benchmark runs."""

    def __init__(self, seed: int = 42):
        random.seed(seed)

    def generate_random_disruption(self) -> DisruptionEvent:
        """Creates a simulated disruption with realistic delay hours and severity."""
        # TODO: Implement randomized event generation based on scenario distributions
        return DisruptionEvent(
            event_id=f"DIS-{random.randint(1000, 9999)}",
            event_type=DisruptionType.PORT_CONGESTION,
            source_entity_id="PORT_MUMBAI_BERTH_2",
            severity_level=0.75,
            delay_hours=4.0,
            description="Port crane maintenance backlog causing 4-hour berth delay"
        )
