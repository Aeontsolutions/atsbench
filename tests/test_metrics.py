import pytest

from atsbench.config import ModelSpec
from atsbench.metrics import cost_usd, percentile


def _spec(pin: float, pout: float) -> ModelSpec:
    return ModelSpec(
        name="x", provider="p", price_per_1m_input=pin, price_per_1m_output=pout
    )


def test_cost_usd():
    # 1000 in @ $2/1M + 500 out @ $10/1M = 0.002 + 0.005 = 0.007
    assert cost_usd(1000, 500, _spec(2.0, 10.0)) == pytest.approx(0.007)


def test_cost_zero_for_free_model():
    assert cost_usd(1234, 5678, _spec(0.0, 0.0)) == 0.0


def test_percentile_basic():
    vals = [10, 20, 30, 40]
    assert percentile(vals, 0) == 10
    assert percentile(vals, 100) == 40
    assert percentile(vals, 50) == pytest.approx(25.0)


def test_percentile_empty_is_zero():
    assert percentile([], 95) == 0.0
