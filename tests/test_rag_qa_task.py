import json
from pathlib import Path

from inspect_ai import eval as inspect_eval
from inspect_ai.model import ModelOutput, get_model

from atsbench.cli import main
from atsbench.tasks.rag_qa import load_dataset, rag_qa_task

ROOT = Path(__file__).resolve().parent.parent
SMOKE = Path(__file__).resolve().parent / "fixtures" / "rag_qa_smoke.jsonl"


def test_load_dataset_puts_qa_in_metadata():
    samples = load_dataset(SMOKE)
    assert len(samples) == 3
    assert "expected_facts" in samples[0].metadata
    assert "context" in samples[0].metadata


def test_full_loop_with_mock_candidate_and_judge(tmp_path, capsys):
    # Mock judge says every expected fact is satisfied -> factfulness 1.0 -> passes gate.
    judge = get_model("mockllm/model", custom_outputs=[
        ModelOutput.from_content(
            "mockllm/model",
            '{"groundedness": {"score": 5, "justification": "ok"}, '
            '"factfulness": {"facts_satisfied": [true, true], "justification": "ok"}, '
            '"goal_completion": {"score": 5, "justification": "ok"}}')
        for _ in range(3)
    ], memoize=False)
    candidate = get_model("mockllm/model", custom_outputs=[
        ModelOutput.from_content("mockllm/model", "A grounded J$ answer.") for _ in range(3)
    ], memoize=False)

    log_dir = tmp_path / "logs"
    inspect_eval(rag_qa_task(dataset_path=str(SMOKE), judge_model=judge),
                 model=candidate, log_dir=str(log_dir))

    json_out = tmp_path / "report.json"
    rc = main(["report", "--logs", str(log_dir), "--workflow", "rag_qa",
               "--models", str(ROOT / "models.yaml"), "--workflows", str(ROOT / "workflows.yaml"),
               "--json", str(json_out)])
    assert rc == 0
    row = json.loads(json_out.read_text())["rows"][0]
    assert row["accuracy"] == 1.0
    assert row["passed_gate"] is True
