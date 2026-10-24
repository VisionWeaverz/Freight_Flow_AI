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


def test_benchmark_runner_execution():
    runner = BenchmarkRunner(runs=5)
    summary = runner.run_benchmark()
    assert summary["total_runs"] == 5
    assert 50.0 <= summary["avg_delay_reduction_pct"] <= 95.0
    assert 80.0 <= summary["conflicts_resolved_pct"] <= 100.0
    assert summary["avg_cost_saved_inr"] > 0
    assert len(summary["records"]) == 5
    for rec in summary["records"]:
        assert "ai_delay_hrs" in rec
        assert "ai_truck_wait_hrs" in rec
        assert "baseline_truck_wait_hrs" in rec
