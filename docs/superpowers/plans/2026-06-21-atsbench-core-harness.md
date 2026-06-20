# atsbench Core Harness (Slice ①) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the reusable core of the atsbench harness — model registry, three-axis scoring math, gated-scorecard verdict, log aggregation, and a zero-cost end-to-end smoke run — so that adding a real workflow (slices ②–⑤) is just a fixture set + a scorer.

**Architecture:** A small Python package on top of Inspect AI. The bug-prone logic (cost/latency math, gate application, Pareto front, ranking, rendering) lives in **pure functions** tested with synthetic inputs and zero Inspect/model dependency. A thin integration layer resolves friendly model names to Inspect model strings, reads Inspect `.eval` logs into typed `RunMetrics`, and a CLI ties it together. An end-to-end smoke test runs a trivial Inspect task through the `mockllm/model` provider (no network, no cost) to prove the whole loop.

**Tech Stack:** Python 3.11+, [Inspect AI](https://inspect.aisi.org.uk/) (`inspect-ai`), Pydantic v2, PyYAML, pytest. Environment managed with **uv** (swappable for Poetry — only the `uv`/`pytest` invocation commands change).

## Global Constraints

- Package name: `atsbench`, `src/` layout (`src/atsbench/`). Python **3.11+**.
- Substrate is **Inspect AI**; do not hand-roll provider/retry/logging code.
- API keys come from **environment variables only** — never written to tracked files. `.env` is git-ignored already.
- **Cost is always computed by us** from token usage × `models.yaml` pricing (never read a provider's own cost field), so every model is costed identically.
- Errored / unparseable samples are **counted and surfaced**, never silently dropped.
- Three co-equal axes everywhere: **accuracy, latency (speed), cost (affordable)**.
- Verdict = per-workflow **gate** (min accuracy + optional max latency / max cost) → **rank** survivors by the workflow's primary axis → **highlight** the Pareto-optimal set.
- Scoring logic is a **pure function**; the Inspect `@scorer` is a thin adapter over it. This is the pattern every later slice copies.

---

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/atsbench/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/test_smoke_import.py`

**Interfaces:**
- Consumes: nothing.
- Produces: an installable `atsbench` package; `uv run pytest` works.

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "atsbench"
version = "0.1.0"
description = "Benchmark any LLM against Aeontsolutions' real workflows on three axes: accurate, fast, affordable."
requires-python = ">=3.11"
dependencies = [
    "inspect-ai>=0.3.50",
    "pydantic>=2.6",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "ruff>=0.5"]

[project.scripts]
atsbench = "atsbench.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/atsbench"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"
```

- [ ] **Step 2: Create the package and test packages**

`src/atsbench/__init__.py`:
```python
"""atsbench — benchmark any LLM against our real workflows on three axes."""

__version__ = "0.1.0"
```

`tests/__init__.py`: (empty file)

- [ ] **Step 3: Write the failing import test**

`tests/test_smoke_import.py`:
```python
def test_package_imports():
    import atsbench

    assert atsbench.__version__ == "0.1.0"
```

- [ ] **Step 4: Install and run the test**

Run:
```bash
uv venv && uv pip install -e ".[dev]"
uv run pytest tests/test_smoke_import.py -v
```
Expected: PASS (1 passed). If `uv` is unavailable, use `python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]" && pytest -v`.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/atsbench/__init__.py tests/__init__.py tests/test_smoke_import.py
git commit -m "feat: scaffold atsbench package"
```

---

### Task 2: Config — model & workflow registries

**Files:**
- Create: `src/atsbench/config.py`
- Create: `models.yaml`
- Create: `workflows.yaml`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `ModelSpec(name: str, provider: str, price_per_1m_input: float, price_per_1m_output: float, trusted: bool = True, notes: str = "")`
  - `WorkflowGate(min_accuracy: float, max_latency_s: float | None = None, max_cost_per_sample_usd: float | None = None, primary_axis: Literal["accuracy","latency","cost"] = "cost")`
  - `WorkflowSpec(name: str, gate: WorkflowGate)`
  - `load_models(path: str | Path) -> dict[str, ModelSpec]` (keyed by `name`)
  - `load_workflows(path: str | Path) -> dict[str, WorkflowSpec]` (keyed by `name`)

- [ ] **Step 1: Write the failing test**

`tests/test_config.py`:
```python
from pathlib import Path

import pytest

from atsbench.config import (
    ModelSpec,
    WorkflowGate,
    load_models,
    load_workflows,
)


def test_load_models(tmp_path: Path):
    (tmp_path / "models.yaml").write_text(
        "models:\n"
        "  - name: gemini-2.5-pro\n"
        "    provider: google/gemini-2.5-pro\n"
        "    price_per_1m_input: 1.25\n"
        "    price_per_1m_output: 10.0\n"
        "  - name: glm-5.2\n"
        "    provider: openai-api/zhipu/glm-5.2\n"
        "    price_per_1m_input: 0.60\n"
        "    price_per_1m_output: 2.20\n"
        "    trusted: false\n"
    )
    models = load_models(tmp_path / "models.yaml")
    assert set(models) == {"gemini-2.5-pro", "glm-5.2"}
    assert models["gemini-2.5-pro"].price_per_1m_output == 10.0
    assert models["gemini-2.5-pro"].trusted is True          # default
    assert models["glm-5.2"].trusted is False


def test_load_workflows(tmp_path: Path):
    (tmp_path / "workflows.yaml").write_text(
        "workflows:\n"
        "  - name: financial_extraction\n"
        "    gate:\n"
        "      min_accuracy: 0.9\n"
        "      max_cost_per_sample_usd: 0.05\n"
        "      primary_axis: cost\n"
    )
    wf = load_workflows(tmp_path / "workflows.yaml")
    assert wf["financial_extraction"].gate.min_accuracy == 0.9
    assert wf["financial_extraction"].gate.max_latency_s is None
    assert wf["financial_extraction"].gate.primary_axis == "cost"


def test_invalid_primary_axis_rejected(tmp_path: Path):
    (tmp_path / "workflows.yaml").write_text(
        "workflows:\n"
        "  - name: bad\n"
        "    gate:\n"
        "      min_accuracy: 0.5\n"
        "      primary_axis: vibes\n"
    )
    with pytest.raises(ValueError):
        load_workflows(tmp_path / "workflows.yaml")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'atsbench.config'`.

- [ ] **Step 3: Write `src/atsbench/config.py`**

```python
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ValidationError


class ModelSpec(BaseModel):
    name: str
    provider: str               # Inspect model string, e.g. "google/gemini-2.5-pro"
    price_per_1m_input: float    # USD per 1M input tokens
    price_per_1m_output: float   # USD per 1M output tokens
    trusted: bool = True         # False => do not send sensitive fixtures here
    notes: str = ""


class WorkflowGate(BaseModel):
    min_accuracy: float
    max_latency_s: float | None = None
    max_cost_per_sample_usd: float | None = None
    primary_axis: Literal["accuracy", "latency", "cost"] = "cost"


class WorkflowSpec(BaseModel):
    name: str
    gate: WorkflowGate


def _load_yaml(path: str | Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def load_models(path: str | Path) -> dict[str, ModelSpec]:
    raw = _load_yaml(path)
    try:
        specs = [ModelSpec(**m) for m in raw["models"]]
    except (ValidationError, KeyError, TypeError) as e:
        raise ValueError(f"Invalid models file {path}: {e}") from e
    return {s.name: s for s in specs}


def load_workflows(path: str | Path) -> dict[str, WorkflowSpec]:
    raw = _load_yaml(path)
    try:
        specs = [WorkflowSpec(**w) for w in raw["workflows"]]
    except (ValidationError, KeyError, TypeError) as e:
        raise ValueError(f"Invalid workflows file {path}: {e}") from e
    return {s.name: s for s in specs}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Create the real `models.yaml` and `workflows.yaml`**

`models.yaml` (prices are representative — confirm against current provider pricing before a real run):
```yaml
# The registry you edit to add a model. provider = Inspect model string.
# OpenAI-compatible endpoints: openai-api/<vendor>/<model> + <VENDOR>_API_KEY and <VENDOR>_BASE_URL env vars.
models:
  - name: gemini-2.5-pro          # current incumbent — benchmarked first to set the baseline
    provider: google/gemini-2.5-pro
    price_per_1m_input: 1.25
    price_per_1m_output: 10.0
    trusted: true
  - name: glm-5.2
    provider: openai-api/zhipu/glm-5.2
    price_per_1m_input: 0.60
    price_per_1m_output: 2.20
    trusted: false                # external — keep sensitive fixtures away from it
  - name: mock                    # zero-cost smoke/CI model
    provider: mockllm/model
    price_per_1m_input: 0.0
    price_per_1m_output: 0.0
    trusted: true
```

`workflows.yaml` (gate numbers are placeholders until the incumbent baseline run in slice ②):
```yaml
workflows:
  - name: smoke                   # the slice-① example workflow
    gate:
      min_accuracy: 0.5
      primary_axis: cost
```

- [ ] **Step 6: Commit**

```bash
git add src/atsbench/config.py tests/test_config.py models.yaml workflows.yaml
git commit -m "feat: model and workflow config registries"
```

---

### Task 3: Cost & latency math (pure functions)

**Files:**
- Create: `src/atsbench/metrics.py`
- Test: `tests/test_metrics.py`

**Interfaces:**
- Consumes: `ModelSpec` (Task 2) for pricing.
- Produces:
  - `cost_usd(input_tokens: int, output_tokens: int, spec: ModelSpec) -> float`
  - `percentile(values: list[float], p: float) -> float` — linear-interpolation percentile, `p` in [0,100]; returns `0.0` for empty input.

- [ ] **Step 1: Write the failing test**

`tests/test_metrics.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_metrics.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'atsbench.metrics'`.

- [ ] **Step 3: Write `src/atsbench/metrics.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_metrics.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/atsbench/metrics.py tests/test_metrics.py
git commit -m "feat: cost and percentile math"
```

---

### Task 4: Gate, Pareto, and ranking (pure functions — the core verdict logic)

**Files:**
- Create: `src/atsbench/scorecard.py`
- Test: `tests/test_scorecard.py`

**Interfaces:**
- Consumes: `WorkflowGate` (Task 2).
- Produces:
  - `RunMetrics` dataclass: `model: str`, `workflow: str`, `accuracy: float`, `latency_p50_s: float`, `latency_p95_s: float`, `cost_per_sample_usd: float`, `n_samples: int`, `n_errors: int`.
  - `passes_gate(m: RunMetrics, gate: WorkflowGate) -> bool`
  - `pareto_front(rows: list[RunMetrics]) -> set[str]` — model names not dominated on (accuracy↑, latency↓, cost↓).
  - `ScorecardRow` dataclass: `metrics: RunMetrics`, `passed_gate: bool`, `is_pareto: bool`, `rank: int | None` (1-based among gate-passers; `None` if failed).
  - `build_scorecard(rows: list[RunMetrics], gate: WorkflowGate) -> list[ScorecardRow]` — ordered: gate-passers first (by primary axis), then failers.

- [ ] **Step 1: Write the failing test**

`tests/test_scorecard.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_scorecard.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'atsbench.scorecard'`.

- [ ] **Step 3: Write `src/atsbench/scorecard.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_scorecard.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/atsbench/scorecard.py tests/test_scorecard.py
git commit -m "feat: gate, pareto, and ranking verdict logic"
```

---

### Task 5: Aggregate a run's samples into RunMetrics (pure) + log walker (thin)

**Files:**
- Create: `src/atsbench/report/__init__.py`
- Create: `src/atsbench/report/aggregate.py`
- Test: `tests/test_aggregate.py`

**Interfaces:**
- Consumes: `ModelSpec` (Task 2), `cost_usd`/`percentile` (Task 3), `RunMetrics` (Task 4).
- Produces:
  - `SampleObs` dataclass: `latency_s: float`, `input_tokens: int`, `output_tokens: int`, `errored: bool`.
  - `aggregate_run(model: str, workflow: str, accuracy: float, samples: list[SampleObs], spec: ModelSpec) -> RunMetrics`
  - `samples_from_log(log) -> list[SampleObs]` — walks an Inspect `EvalLog`'s samples (integration-covered by Task 7's smoke test).
  - `accuracy_from_log(log) -> float` — reads the `accuracy` metric from `log.results`.

- [ ] **Step 1: Write the failing test (pure aggregator only)**

`tests/test_aggregate.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_aggregate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'atsbench.report'`.

- [ ] **Step 3: Write `src/atsbench/report/__init__.py` (empty) and `src/atsbench/report/aggregate.py`**

`src/atsbench/report/__init__.py`: (empty file)

`src/atsbench/report/aggregate.py`:
```python
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


def samples_from_log(log) -> list[SampleObs]:
    """Walk an Inspect EvalLog into SampleObs. Token usage is summed across any
    models the sample touched; latency uses working_time, falling back to total_time."""
    obs: list[SampleObs] = []
    for sample in log.samples or []:
        usage = sample.model_usage or {}
        input_tokens = sum(u.input_tokens for u in usage.values())
        output_tokens = sum(u.output_tokens for u in usage.values())
        latency = sample.working_time or sample.total_time or 0.0
        obs.append(
            SampleObs(
                latency_s=float(latency),
                input_tokens=int(input_tokens),
                output_tokens=int(output_tokens),
                errored=sample.error is not None,
            )
        )
    return obs


def accuracy_from_log(log) -> float:
    """Read the 'accuracy' metric from the first scorer in log.results."""
    if log.results is None or not log.results.scores:
        return 0.0
    for score in log.results.scores:
        metric = score.metrics.get("accuracy")
        if metric is not None:
            return float(metric.value)
    return 0.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_aggregate.py -v`
Expected: PASS (2 passed). (`samples_from_log`/`accuracy_from_log` are exercised end-to-end in Task 7.)

- [ ] **Step 5: Commit**

```bash
git add src/atsbench/report/__init__.py src/atsbench/report/aggregate.py tests/test_aggregate.py
git commit -m "feat: aggregate samples into RunMetrics + Inspect log walkers"
```

---

### Task 6: Render the scorecard (markdown + JSON)

**Files:**
- Create: `src/atsbench/report/render.py`
- Test: `tests/test_render.py`

**Interfaces:**
- Consumes: `ScorecardRow` (Task 4).
- Produces:
  - `render_markdown(workflow: str, card: list[ScorecardRow]) -> str`
  - `render_json(workflow: str, card: list[ScorecardRow]) -> dict`

- [ ] **Step 1: Write the failing test**

`tests/test_render.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_render.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'atsbench.report.render'`.

- [ ] **Step 3: Write `src/atsbench/report/render.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_render.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/atsbench/report/render.py tests/test_render.py
git commit -m "feat: markdown and json scorecard renderers"
```

---

### Task 7: Reference scorer + example task + CLI + end-to-end smoke

**Files:**
- Create: `src/atsbench/scorers/__init__.py`
- Create: `src/atsbench/scorers/exact_match.py`
- Create: `src/atsbench/tasks/__init__.py`
- Create: `src/atsbench/tasks/smoke.py`
- Create: `src/atsbench/report/build.py`
- Create: `src/atsbench/cli.py`
- Test: `tests/test_exact_match.py`
- Test: `tests/test_end_to_end.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `normalize(s: str) -> str` and `exact_match_score(output: str, target: str) -> bool` (pure).
  - `exact_match()` — Inspect `@scorer` adapter (the template later slices copy).
  - `smoke_task()` — an Inspect `@task` runnable against `mockllm/model`.
  - `build_scorecard_for_logs(log_dir, workflow, models) -> list[ScorecardRow]`.
  - `main()` — CLI entry point: `atsbench report --logs DIR --workflow NAME [--json OUT]`.

- [ ] **Step 1: Write the failing pure-scorer test**

`tests/test_exact_match.py`:
```python
from atsbench.scorers.exact_match import exact_match_score, normalize


def test_normalize_strips_and_lowercases():
    assert normalize("  Hello World  ") == "hello world"


def test_exact_match_score():
    assert exact_match_score("Yes", "yes") is True
    assert exact_match_score("no", "yes") is False
```

- [ ] **Step 2: Run it; verify it fails**

Run: `uv run pytest tests/test_exact_match.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'atsbench.scorers'`.

- [ ] **Step 3: Write the scorer (pure logic + thin adapter)**

`src/atsbench/scorers/__init__.py`: (empty file)

`src/atsbench/scorers/exact_match.py`:
```python
from __future__ import annotations

from inspect_ai.scorer import (
    CORRECT,
    INCORRECT,
    Score,
    Target,
    accuracy,
    scorer,
    stderr,
)
from inspect_ai.solver import TaskState


def normalize(s: str) -> str:
    return " ".join(s.strip().lower().split())


def exact_match_score(output: str, target: str) -> bool:
    return normalize(output) == normalize(target)


@scorer(metrics=[accuracy(), stderr()])
def exact_match():
    """Template scorer: pure logic + thin Inspect adapter. Later slices copy this shape."""

    async def score(state: TaskState, target: Target) -> Score:
        output = state.output.completion
        correct = exact_match_score(output, target.text)
        return Score(
            value=CORRECT if correct else INCORRECT,
            answer=output,
            explanation=f"normalized output vs target: {normalize(output)!r} == {normalize(target.text)!r}",
        )

    return score
```

- [ ] **Step 4: Run it; verify it passes**

Run: `uv run pytest tests/test_exact_match.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Write the example task**

`src/atsbench/tasks/__init__.py`: (empty file)

`src/atsbench/tasks/smoke.py`:
```python
from __future__ import annotations

from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.solver import generate

from atsbench.scorers.exact_match import exact_match


@task
def smoke_task() -> Task:
    """Trivial task to prove the loop end-to-end with the mock provider."""
    return Task(
        dataset=[
            Sample(input="Reply with exactly: ok", target="ok"),
            Sample(input="Reply with exactly: ok", target="ok"),
        ],
        solver=generate(),
        scorer=exact_match(),
    )
```

- [ ] **Step 6: Write the log→scorecard builder**

`src/atsbench/report/build.py`:
```python
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
```

- [ ] **Step 7: Write the CLI**

`src/atsbench/cli.py`:
```python
from __future__ import annotations

import argparse
import json
import sys

from atsbench.config import load_models, load_workflows
from atsbench.report.build import build_scorecard_for_logs
from atsbench.report.render import render_json, render_markdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="atsbench")
    sub = parser.add_subparsers(dest="command", required=True)

    rep = sub.add_parser("report", help="Aggregate eval logs into a gated scorecard.")
    rep.add_argument("--logs", required=True, help="Directory of Inspect .eval logs.")
    rep.add_argument("--workflow", required=True, help="Workflow name in workflows.yaml.")
    rep.add_argument("--models", default="models.yaml")
    rep.add_argument("--workflows", default="workflows.yaml")
    rep.add_argument("--json", dest="json_out", help="Optional path to write JSON.")

    args = parser.parse_args(argv)

    if args.command == "report":
        models = load_models(args.models)
        workflows = load_workflows(args.workflows)
        if args.workflow not in workflows:
            print(f"Unknown workflow: {args.workflow}", file=sys.stderr)
            return 2
        wf = workflows[args.workflow]
        card = build_scorecard_for_logs(args.logs, wf, models)
        print(render_markdown(wf.name, card))
        if args.json_out:
            with open(args.json_out, "w") as f:
                json.dump(render_json(wf.name, card), f, indent=2)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 8: Write the end-to-end smoke test**

`tests/test_end_to_end.py`:
```python
from pathlib import Path

from inspect_ai import eval as inspect_eval

from atsbench.cli import main
from atsbench.tasks.smoke import smoke_task


def test_full_loop_with_mock_model(tmp_path: Path, capsys):
    log_dir = tmp_path / "logs"
    # Run the trivial task through the zero-cost mock provider.
    inspect_eval(smoke_task(), model="mockllm/model", log_dir=str(log_dir))
    assert any(log_dir.iterdir()), "expected an .eval log to be written"

    # The CLI should read the log and emit a scorecard for the 'smoke' workflow.
    rc = main(["report", "--logs", str(log_dir), "--workflow", "smoke",
               "--models", "models.yaml", "--workflows", "workflows.yaml"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "# smoke" in out
    assert "mockllm/model" in out
```

- [ ] **Step 9: Run the full suite**

Run: `uv run pytest -v`
Expected: PASS (all tests). The end-to-end test makes **no network calls** — `mockllm/model` is local.
If `inspect_eval`'s signature differs in the installed version, run `uv run python -c "from inspect_ai import eval; help(eval)"` and adjust the `model=`/`log_dir=` kwargs accordingly, then re-run.

- [ ] **Step 10: Manually exercise the CLI**

Run:
```bash
uv run python -c "from inspect_ai import eval; from atsbench.tasks.smoke import smoke_task; eval(smoke_task(), model='mockllm/model', log_dir='logs/smoke')"
uv run atsbench report --logs logs/smoke --workflow smoke --json out.json
```
Expected: a markdown scorecard table printed with a `mockllm/model` row, and `out.json` written. (`logs/` is git-ignored.)

- [ ] **Step 11: Commit**

```bash
git add src/atsbench/scorers src/atsbench/tasks src/atsbench/report/build.py src/atsbench/cli.py tests/test_exact_match.py tests/test_end_to_end.py
git commit -m "feat: reference scorer, smoke task, report CLI, end-to-end loop"
```

---

## Self-Review

**Spec coverage (slice ① scope = core + mock provider + report aggregator + scorer pattern):**
- Model registry / provider resolution → Task 2 (`config.py`, `models.yaml`) + Task 7 (`_spec_for_model`). ✓
- Three co-equal axes (accuracy/latency/cost) → Task 3 (cost, percentile) + Task 5 (aggregate). ✓
- Gate → rank → Pareto verdict → Task 4. ✓
- Cost computed by us from tokens × pricing → Task 3 `cost_usd`, used in Task 5. ✓
- Errored samples counted, not dropped → `n_errors` in Task 4/5. ✓
- Report markdown + JSON → Task 6. ✓
- Mock provider / zero-cost end-to-end → Task 7 (`mockllm/model`). ✓
- Scorer pattern (pure fn + thin `@scorer`) for later slices → Task 7 reference scorer. ✓
- Inspect task scaffolding → Task 7 `smoke_task`. ✓
- Per-workflow gate config → Task 2 `workflows.yaml`. ✓
- Data-governance `trusted` flag forward-declared → Task 2 `ModelSpec.trusted` (enforced in fixture slices). Deferred by design.

**Out of slice ① (own later plans):** the four real workflows' fixtures + scorers (financial extraction, classification, RAG Q&A judge, text-to-SQL), `atsbench run`/`compare` live-model invocation, and setting real gate numbers after the incumbent baseline.

**Placeholder scan:** No "TBD"/"add error handling here". `models.yaml` prices and `workflows.yaml` gate numbers are user-maintained config data, explicitly flagged to confirm before a real run — not code placeholders.

**Type consistency:** `RunMetrics` fields are identical across Tasks 4/5/6. `ScorecardRow(metrics, passed_gate, is_pareto, rank)` consistent across Tasks 4/6/7. `SampleObs` consistent across Task 5/7. `ModelSpec`/`WorkflowSpec` consistent across Tasks 2/5/7. Scorer returns `Score`; aggregator reads the `accuracy` metric the `@scorer(metrics=[accuracy(), ...])` declares. ✓
