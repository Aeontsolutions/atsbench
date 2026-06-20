from __future__ import annotations

from atsbench.config import ModelSpec


def cost_usd(input_tokens: int, output_tokens: int, spec: ModelSpec) -> float:
    """Cost of one sample, computed from token counts and registry pricing."""
    return (
        input_tokens / 1_000_000 * spec.price_per_1m_input
        + output_tokens / 1_000_000 * spec.price_per_1m_output
    )


def percentile(values: list[float], p: float) -> float:
    """Linear-interpolation percentile. p in [0, 100]. Empty -> 0.0."""
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (p / 100) * (len(ordered) - 1)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    frac = rank - low
    return float(ordered[low] + (ordered[high] - ordered[low]) * frac)
