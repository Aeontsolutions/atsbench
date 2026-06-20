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
