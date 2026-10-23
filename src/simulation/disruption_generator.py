"""Synthetic disruption generator for port ETA shifts, traffic jams, and breakdowns."""

import random
from typing import List, Optional
from datetime import datetime
from src.common.schemas import DisruptionEvent, DisruptionType


class DisruptionGenerator:
    """Generates stochastic disruption events for testing and benchmark runs."""

    DISRUPTION_SCENARIOS = [
        (
            DisruptionType.PORT_CONGESTION,
            "Berth crane maintenance backlog and vessel queue at container terminal",
            (2.0, 5.5),
            (0.60, 0.90)
        ),
        (
            DisruptionType.TRUCK_BREAKDOWN,
            "Tractor engine cooling failure on national freight highway corridor",
            (1.5, 4.0),
            (0.50, 0.85)
        ),
        (
            DisruptionType.TRAFFIC_INCIDENT,
            "Multi-vehicle accident and severe monsoon waterlogging on arterial expressway",
            (1.0, 3.5),
            (0.40, 0.75)
        ),
        (
            DisruptionType.WAREHOUSE_BOTTLENECK,
            "Dock door hydraulic failure and intake buffer congestion at fulfillment center",
            (2.0, 4.5),
            (0.55, 0.80)
        ),
        (
            DisruptionType.VESSEL_DELAY,
            "Offshore fog advisory and maritime navigation slowdown",
            (3.0, 6.0),
            (0.65, 0.95)
        ),
    ]

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)

    def generate_random_disruption(self, run_index: int = 1, shipment_id: Optional[str] = None) -> DisruptionEvent:
        """Creates a realistic simulated disruption with stochastic severity and delay."""
        dtype, desc_template, delay_range, sev_range = self.rng.choice(self.DISRUPTION_SCENARIOS)
        
        delay_hours = round(self.rng.uniform(delay_range[0], delay_range[1]), 1)
        severity = round(self.rng.uniform(sev_range[0], sev_range[1]), 2)
        
        # If no shipment specified, pick a deterministic cohort ID
        entity_id = shipment_id or f"SHP-{1000 + (run_index % 25) + 1}"
        
        return DisruptionEvent(
            event_id=f"DIS-RUN-{run_index:03d}",
            event_type=dtype,
            source_entity_id=entity_id,
            severity_level=severity,
            delay_hours=delay_hours,
            reported_at=datetime.utcnow(),
            description=f"{desc_template} (Estimated delay: +{delay_hours} hrs)",
            metadata={"run_index": run_index}
        )

    def generate_benchmark_batch(self, count: int = 50) -> List[DisruptionEvent]:
        """Generates a batch of N disruption events for benchmarking."""
        return [self.generate_random_disruption(run_index=i + 1) for i in range(count)]
