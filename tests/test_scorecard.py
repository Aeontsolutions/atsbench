from atsbench.config import WorkflowGate
from atsbench.scorecard import (
    RunMetrics,
    build_scorecard,
    pareto_front,
    passes_gate,
)


def _m(model, acc, p50, p95, cost, n=10, err=0):
    return RunMetrics(
        model=model, workflow="w", accuracy=acc,
        latency_p50_s=p50, latency_p95_s=p95,
        cost_per_sample_usd=cost, n_samples=n, n_errors=err,
    )


def test_passes_gate_accuracy_floor():
    gate = WorkflowGate(min_accuracy=0.9)
    assert passes_gate(_m("a", 0.95, 1, 2, 0.01), gate) is True
    assert passes_gate(_m("b", 0.80, 1, 2, 0.01), gate) is False


def test_passes_gate_latency_and_cost_budgets():
    gate = WorkflowGate(min_accuracy=0.5, max_latency_s=3.0, max_cost_per_sample_usd=0.02)
    assert passes_gate(_m("ok", 0.9, 1.0, 2.5, 0.01), gate) is True
    assert passes_gate(_m("slow", 0.9, 1.0, 4.0, 0.01), gate) is False   # p95 > 3.0
    assert passes_gate(_m("pricey", 0.9, 1.0, 2.5, 0.03), gate) is False  # cost > 0.02


def test_pareto_front():
    rows = [
        _m("cheap_accurate", 0.95, 1.0, 1.5, 0.001),  # dominates all -> on front
        _m("dominated", 0.90, 2.0, 3.0, 0.010),       # worse on every axis
        _m("fast_pricey", 0.80, 0.2, 0.3, 0.050),     # best latency -> on front
    ]
    front = pareto_front(rows)
    assert "cheap_accurate" in front
    assert "fast_pricey" in front
    assert "dominated" not in front


def test_build_scorecard_orders_passers_by_primary_axis():
    gate = WorkflowGate(min_accuracy=0.9, primary_axis="cost")
    rows = [
        _m("expensive", 0.95, 1, 2, 0.05),
        _m("cheap", 0.95, 1, 2, 0.01),
        _m("failer", 0.50, 1, 2, 0.001),
    ]
    card = build_scorecard(rows, gate)
    passers = [r for r in card if r.passed_gate]
    assert [r.metrics.model for r in passers] == ["cheap", "expensive"]
    assert passers[0].rank == 1 and passers[1].rank == 2
    failer = [r for r in card if not r.passed_gate][0]
    assert failer.metrics.model == "failer" and failer.rank is None
