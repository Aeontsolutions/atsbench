import json
from pathlib import Path

from inspect_ai import eval as inspect_eval
from inspect_ai.model import ModelOutput, get_model

from atsbench.cli import main
from atsbench.tasks.smoke import smoke_task

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_full_loop_with_mock_model(tmp_path: Path, capsys):
    log_dir = tmp_path / "logs"
    # Drive the mock to return the correct answer for each sample so the model
    # PASSES the smoke gate. This exercises the success path (accuracy, gate
    # pass, rank, passers-sort) end to end — zero-cost, no network.
    model = get_model(
        "mockllm/model",
        custom_outputs=[
            ModelOutput.from_content("mockllm/model", "ok"),
            ModelOutput.from_content("mockllm/model", "ok"),
        ],
        memoize=False,
    )
    inspect_eval(smoke_task(), model=model, log_dir=str(log_dir))
    assert any(log_dir.iterdir()), "expected an .eval log to be written"

    json_out = tmp_path / "report.json"
    rc = main(["report", "--logs", str(log_dir), "--workflow", "smoke",
               "--models", str(REPO_ROOT / "models.yaml"),
               "--workflows", str(REPO_ROOT / "workflows.yaml"),
               "--json", str(json_out)])
    assert rc == 0

    out = capsys.readouterr().out
    assert "# smoke" in out
    assert "mockllm/model" in out

    data = json.loads(json_out.read_text())
    row = data["rows"][0]
    assert row["model"] == "mockllm/model"
    assert row["accuracy"] == 1.0      # cleared the gate
    assert row["passed_gate"] is True
    assert row["rank"] == 1
