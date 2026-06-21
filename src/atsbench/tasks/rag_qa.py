from __future__ import annotations

import json
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.model import Model
from inspect_ai.solver import generate, system_message

from atsbench.scorers.rag_qa import DEFAULT_JUDGE, rag_qa_judge

_FIXTURES = Path(__file__).resolve().parent.parent.parent.parent / "fixtures" / "rag_qa"
_PROMPT_PATH = _FIXTURES / "system_prompt.txt"
_DEFAULT_DATASET = _FIXTURES / "dataset.jsonl"

# faithful single-turn rendering of the production financial-synthesis turn
USER_TEMPLATE = (
    "{question}\n\n"
    "Financial data retrieved from the JSE database:\n{context}\n\n"
    "Answer the user's question using ONLY this data. Use J$ and include a brief "
    "investment disclaimer."
)


def load_dataset(path) -> list[Sample]:
    samples = []
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec["category"] == "negative":
            user = rec["question"]
        else:
            user = USER_TEMPLATE.format(question=rec["question"], context=rec["context"])
        samples.append(Sample(
            id=rec["id"], input=user,
            metadata={"question": rec["question"], "context": rec["context"],
                      "expected_facts": rec["expected_facts"], "category": rec["category"]},
        ))
    return samples


@task
def rag_qa_task(dataset_path=None, judge_model: "str | Model" = DEFAULT_JUDGE) -> Task:
    return Task(
        dataset=load_dataset(dataset_path or _DEFAULT_DATASET),
        solver=[system_message(_PROMPT_PATH.read_text()), generate()],
        scorer=rag_qa_judge(judge_model),
    )
