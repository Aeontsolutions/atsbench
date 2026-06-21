from __future__ import annotations

from dataclasses import dataclass

from atsbench.config import ModelSpec
from atsbench.metrics import cost_usd, percentile
from atsbench.scorecard import RunMetrics


@dataclass
class SampleObs:
    latency_s: float
    input_tokens: int
    output_tokens: int
    errored: bool


def aggregate_run(
    model: str,
    workflow: str,
    accuracy: float,
    samples: list[SampleObs],
    spec: ModelSpec,
) -> RunMetrics:
    latencies = [s.latency_s for s in samples]
    costs = [cost_usd(s.input_tokens, s.output_tokens, spec) for s in samples]
    mean_cost = sum(costs) / len(costs) if costs else 0.0
    return RunMetrics(
        model=model,
        workflow=workflow,
        accuracy=accuracy,
        latency_p50_s=percentile(latencies, 50),
        latency_p95_s=percentile(latencies, 95),
        cost_per_sample_usd=mean_cost,
        n_samples=len(samples),
        n_errors=sum(1 for s in samples if s.errored),
    )


def samples_from_log(log, candidate_model: str) -> list[SampleObs]:
    """Walk an Inspect EvalLog into SampleObs, counting ONLY the candidate model's
    tokens (a model-graded scorer's judge calls also land in sample.model_usage)."""
    obs: list[SampleObs] = []
    for sample in log.samples or []:
        usage = sample.model_usage or {}
        input_tokens = sum(u.input_tokens for k, u in usage.items() if k == candidate_model)
        output_tokens = sum(u.output_tokens for k, u in usage.items() if k == candidate_model)
        latency = sample.working_time or sample.total_time or 0.0
        obs.append(SampleObs(latency_s=float(latency), input_tokens=int(input_tokens),
                             output_tokens=int(output_tokens), errored=sample.error is not None))
    return obs


def accuracy_from_log(log) -> float:
    """Headline accuracy: prefer an 'accuracy' metric, then 'mean', then the
    first metric on the first scorer. Float-valued scorers (e.g. classification's
    macro per-field accuracy via mean()) surface their headline this way."""
    if log.results is None or not log.results.scores:
        return 0.0
    for score in log.results.scores:
        for key in ("accuracy", "mean"):
            metric = score.metrics.get(key)
            if metric is not None:
                return float(metric.value)
    first = log.results.scores[0].metrics
    if first:
        return float(next(iter(first.values())).value)
    return 0.0
