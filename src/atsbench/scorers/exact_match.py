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
