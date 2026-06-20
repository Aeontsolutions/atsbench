from atsbench.report.render import render_json, render_markdown
from atsbench.scorecard import RunMetrics, ScorecardRow


def _row(model, acc, cost, passed, pareto, rank):
    return ScorecardRow(
        metrics=RunMetrics(
            model=model, workflow="w", accuracy=acc,
            latency_p50_s=1.0, latency_p95_s=2.0,
            cost_per_sample_usd=cost, n_samples=10, n_errors=0,
        ),
        passed_gate=passed, is_pareto=pareto, rank=rank,
    )


def test_render_markdown_marks_pareto_and_gate():
    card = [
        _row("cheap", 0.95, 0.01, passed=True, pareto=True, rank=1),
        _row("failer", 0.50, 0.001, passed=False, pareto=False, rank=None),
    ]
    md = render_markdown("smoke", card)
    assert "# smoke" in md
    assert "cheap" in md and "failer" in md
    assert "★" in md           # pareto marker present
    assert "FAIL" in md        # gate failure shown


def test_render_json_roundtrips_fields():
    card = [_row("cheap", 0.95, 0.01, passed=True, pareto=True, rank=1)]
    data = render_json("smoke", card)
    assert data["workflow"] == "smoke"
    assert data["rows"][0]["model"] == "cheap"
    assert data["rows"][0]["passed_gate"] is True
    assert data["rows"][0]["rank"] == 1
