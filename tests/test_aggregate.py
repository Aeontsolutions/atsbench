import pytest

from atsbench.config import ModelSpec
from atsbench.report.aggregate import SampleObs, aggregate_run


def test_aggregate_run_computes_axes():
    spec = ModelSpec(name="m", provider="p", price_per_1m_input=2.0, price_per_1m_output=10.0)
    samples = [
        SampleObs(latency_s=1.0, input_tokens=1000, output_tokens=500, errored=False),
        SampleObs(latency_s=3.0, input_tokens=1000, output_tokens=500, errored=False),
        SampleObs(latency_s=2.0, input_tokens=1000, output_tokens=500, errored=True),
    ]
    rm = aggregate_run("m", "w", accuracy=0.8, samples=samples, spec=spec)
    assert rm.n_samples == 3
    assert rm.n_errors == 1
    assert rm.accuracy == 0.8
    # mean cost/sample = 0.007 (each sample 1000 in + 500 out)
    assert rm.cost_per_sample_usd == pytest.approx(0.007)
    assert rm.latency_p50_s == pytest.approx(2.0)
    assert rm.latency_p95_s == pytest.approx(2.9)  # p95 of [1,2,3] interpolated


def test_aggregate_run_handles_no_samples():
    spec = ModelSpec(name="m", provider="p", price_per_1m_input=1.0, price_per_1m_output=1.0)
    rm = aggregate_run("m", "w", accuracy=0.0, samples=[], spec=spec)
    assert rm.n_samples == 0
    assert rm.cost_per_sample_usd == 0.0
    assert rm.latency_p95_s == 0.0
