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
