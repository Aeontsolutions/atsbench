from __future__ import annotations

from atsbench.scorecard import ScorecardRow


def render_markdown(workflow: str, card: list[ScorecardRow]) -> str:
    lines = [
        f"# {workflow}",
        "",
        "| Rank | Model | Accuracy | p50 (s) | p95 (s) | $/sample | Gate | Pareto |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in card:
        m = r.metrics
        rank = str(r.rank) if r.rank is not None else "—"
        gate = "pass" if r.passed_gate else "**FAIL**"
        pareto = "★" if r.is_pareto else ""
        lines.append(
            f"| {rank} | {m.model} | {m.accuracy:.3f} | {m.latency_p50_s:.2f} | "
            f"{m.latency_p95_s:.2f} | ${m.cost_per_sample_usd:.4f} | {gate} | {pareto} |"
        )
    lines.append("")
    lines.append("★ = Pareto-optimal (cannot improve one axis without sacrificing another).")
    return "\n".join(lines)


def render_json(workflow: str, card: list[ScorecardRow]) -> dict:
    return {
        "workflow": workflow,
        "rows": [
            {
                "model": r.metrics.model,
                "accuracy": r.metrics.accuracy,
                "latency_p50_s": r.metrics.latency_p50_s,
                "latency_p95_s": r.metrics.latency_p95_s,
                "cost_per_sample_usd": r.metrics.cost_per_sample_usd,
                "n_samples": r.metrics.n_samples,
                "n_errors": r.metrics.n_errors,
                "passed_gate": r.passed_gate,
                "is_pareto": r.is_pareto,
                "rank": r.rank,
            }
            for r in card
        ],
    }
