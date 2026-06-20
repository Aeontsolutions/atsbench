from __future__ import annotations

from dataclasses import dataclass

from atsbench.config import WorkflowGate


@dataclass
class RunMetrics:
    model: str
    workflow: str
    accuracy: float
    latency_p50_s: float
    latency_p95_s: float
    cost_per_sample_usd: float
    n_samples: int
    n_errors: int


@dataclass
class ScorecardRow:
    metrics: RunMetrics
    passed_gate: bool
    is_pareto: bool
    rank: int | None


def passes_gate(m: RunMetrics, gate: WorkflowGate) -> bool:
    if m.accuracy < gate.min_accuracy:
        return False
    if gate.max_latency_s is not None and m.latency_p95_s > gate.max_latency_s:
        return False
    if (
        gate.max_cost_per_sample_usd is not None
        and m.cost_per_sample_usd > gate.max_cost_per_sample_usd
    ):
        return False
    return True


def _dominates(a: RunMetrics, b: RunMetrics) -> bool:
    """a dominates b: no worse on every axis, strictly better on at least one.
    Axes: accuracy (higher better), latency_p95 (lower better), cost (lower better)."""
    no_worse = (
        a.accuracy >= b.accuracy
        and a.latency_p95_s <= b.latency_p95_s
        and a.cost_per_sample_usd <= b.cost_per_sample_usd
    )
    strictly_better = (
        a.accuracy > b.accuracy
        or a.latency_p95_s < b.latency_p95_s
        or a.cost_per_sample_usd < b.cost_per_sample_usd
    )
    return no_worse and strictly_better


def pareto_front(rows: list[RunMetrics]) -> set[str]:
    front: set[str] = set()
    for a in rows:
        if not any(_dominates(b, a) for b in rows if b is not a):
            front.add(a.model)
    return front


def _primary_key(m: RunMetrics, axis: str):
    if axis == "cost":
        return m.cost_per_sample_usd            # ascending
    if axis == "latency":
        return m.latency_p95_s                  # ascending
    return -m.accuracy                          # accuracy: higher first


def build_scorecard(rows: list[RunMetrics], gate: WorkflowGate) -> list[ScorecardRow]:
    front = pareto_front(rows)
    passers = [m for m in rows if passes_gate(m, gate)]
    failers = [m for m in rows if not passes_gate(m, gate)]
    passers.sort(key=lambda m: _primary_key(m, gate.primary_axis))

    out: list[ScorecardRow] = []
    for i, m in enumerate(passers, start=1):
        out.append(ScorecardRow(m, passed_gate=True, is_pareto=m.model in front, rank=i))
    for m in failers:
        out.append(ScorecardRow(m, passed_gate=False, is_pareto=m.model in front, rank=None))
    return out
