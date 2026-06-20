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
