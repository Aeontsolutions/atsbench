from __future__ import annotations

from pathlib import Path

from inspect_ai.log import list_eval_logs, read_eval_log

from atsbench.config import ModelSpec, WorkflowSpec
from atsbench.report.aggregate import (
    accuracy_from_log,
    aggregate_run,
    samples_from_log,
)
from atsbench.scorecard import ScorecardRow, build_scorecard


def _spec_for_model(model: str, models: dict[str, ModelSpec]) -> ModelSpec:
    # Match by friendly name or by full provider string.
    for spec in models.values():
        if model in (spec.name, spec.provider):
            return spec
    # Unknown model: cost defaults to 0 so it still appears (flagged by name).
    return ModelSpec(name=model, provider=model, price_per_1m_input=0.0, price_per_1m_output=0.0)


def build_scorecard_for_logs(
    log_dir: str | Path,
    workflow: WorkflowSpec,
    models: dict[str, ModelSpec],
) -> list[ScorecardRow]:
    rows = []
    for info in list_eval_logs(str(log_dir)):
        log = read_eval_log(info)
        if log.status != "success":
            continue
        model = log.eval.model
        spec = _spec_for_model(model, models)
        rm = aggregate_run(
            model=model,
            workflow=workflow.name,
            accuracy=accuracy_from_log(log),
            samples=samples_from_log(log),
            spec=spec,
        )
        rows.append(rm)
    return build_scorecard(rows, workflow.gate)
