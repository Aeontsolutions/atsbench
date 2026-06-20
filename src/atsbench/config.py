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
