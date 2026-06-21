import json
from pathlib import Path

from inspect_ai import eval as inspect_eval
from inspect_ai.model import ModelOutput, get_model

from atsbench.cli import main
from atsbench.tasks.classification import classification_task, load_dataset

ROOT = Path(__file__).resolve().parent.parent
SMOKE = Path(__file__).resolve().parent / "fixtures" / "classification_smoke.jsonl"


def test_load_dataset_reads_records():
    samples = load_dataset(SMOKE)
    assert len(samples) == 3
    assert samples[0].metadata["golden"]["symbol"] == "BIL"


def test_real_dataset_loads_cleanly():
    samples = load_dataset(ROOT / "fixtures" / "classification" / "dataset.jsonl")
    assert len(samples) == 70
    for s in samples:
        g = s.metadata["golden"]
        assert set(g) == {"is_financial", "document_type", "company", "symbol", "year", "audited"}
        assert isinstance(g["year"], str)


def test_full_loop_with_mock_model(tmp_path, capsys):
    # Mock returns the exactly-correct classification JSON for each of the 3 docs,
    # so the model scores 1.0 and passes the gate — exercises the success path.
    golden = [json.loads(line)["golden"] for line in SMOKE.read_text().splitlines()]
    outputs = [ModelOutput.from_content("mockllm/model", json.dumps(g)) for g in golden]
    model = get_model("mockllm/model", custom_outputs=outputs, memoize=False)

    log_dir = tmp_path / "logs"
    inspect_eval(classification_task(dataset_path=str(SMOKE)), model=model, log_dir=str(log_dir))

    json_out = tmp_path / "report.json"
    rc = main(["report", "--logs", str(log_dir), "--workflow", "classification",
               "--models", str(ROOT / "models.yaml"), "--workflows", str(ROOT / "workflows.yaml"),
               "--json", str(json_out)])
    assert rc == 0
    row = json.loads(json_out.read_text())["rows"][0]
    assert row["accuracy"] == 1.0
    assert row["passed_gate"] is True
