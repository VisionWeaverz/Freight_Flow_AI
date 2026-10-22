"""Tests for disruption generator and simulation benchmark harness."""

from src.simulation.disruption_generator import DisruptionGenerator
from src.simulation.benchmark_runner import BenchmarkRunner


def test_disruption_generator():
    generator = DisruptionGenerator(seed=123)
    event = generator.generate_random_disruption()
    assert event.event_id.startswith("DIS-")
    assert event.delay_hours > 0


def test_benchmark_runner_init():
    runner = BenchmarkRunner(runs=5)
    assert runner.runs == 5
