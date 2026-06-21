from __future__ import annotations

import json
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.solver import generate, system_message

from atsbench.scorers.classification import classification

_FIXTURES = Path(__file__).resolve().parent.parent.parent.parent / "fixtures" / "classification"
_PROMPT_PATH = _FIXTURES / "system_prompt.txt"
_DEFAULT_DATASET = _FIXTURES / "dataset.jsonl"

USER_TEMPLATE = (
    'Please analyze and classify this document named "{filename}".\n\n'
    "Document content:\n{text}"
)


def _system_prompt() -> str:
    return _PROMPT_PATH.read_text()


def load_dataset(path: str | Path) -> list[Sample]:
    samples = []
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        user = USER_TEMPLATE.format(filename=rec["source_filename"], text=rec["input_text"])
        samples.append(Sample(id=rec["id"], input=user, metadata={"golden": rec["golden"]}))
    return samples


@task
def classification_task(dataset_path: str | Path | None = None) -> Task:
    return Task(
        dataset=load_dataset(dataset_path or _DEFAULT_DATASET),
        solver=[system_message(_system_prompt()), generate()],
        scorer=classification(),
    )
