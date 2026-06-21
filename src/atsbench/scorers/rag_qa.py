from __future__ import annotations

import json

from inspect_ai.model import Model, get_model
from inspect_ai.scorer import Score, Target, mean, scorer, stderr
from inspect_ai.solver import TaskState

DEFAULT_JUDGE = "openrouter/anthropic/claude-3.7-sonnet"  # neutral; confirm slug at openrouter.ai/models

JUDGE_TEMPLATE = """You are an expert evaluator of a financial chatbot's single answer.

# Question
{question}

# Retrieved context the answer must rely on
{context}

# Answer under evaluation
{answer}

# Expected facts (a good answer should satisfy each)
{expected_facts}

# Scoring
Score each dimension 1-5 (integer). For factfulness, decide for EACH expected fact
whether the answer satisfies it (true/false), in the same order as listed above.
- groundedness: are the answer's claims supported by the retrieved context? 5 = every
  figure/entity is traceable to the context; 1 = mostly unsupported or contradicts it.
- goal_completion: did the answer actually address the question? 5 = fully; 1 = not at all.

Respond ONLY with valid JSON, no other text:
{{
  "groundedness": {{"score": <int>, "justification": "<str>"}},
  "factfulness": {{"facts_satisfied": [<bool>, ...], "justification": "<str>"}},
  "goal_completion": {{"score": <int>, "justification": "<str>"}}
}}"""


def parse_judge_output(raw: str) -> dict | None:
    try:
        return json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
    except (ValueError, json.JSONDecodeError):
        return None


def facts_fraction(judge: dict) -> float:
    facts = (judge.get("factfulness") or {}).get("facts_satisfied") or []
    if not facts:
        return 0.0
    return sum(1 for f in facts if f) / len(facts)


def _dim_score(judge: dict, name: str):
    return (judge.get(name) or {}).get("score")


@scorer(metrics=[mean(), stderr()])
def rag_qa_judge(judge_model: "str | Model" = DEFAULT_JUDGE):
    model = judge_model if isinstance(judge_model, Model) else get_model(judge_model)

    async def score(state: TaskState, target: Target) -> Score:
        md = state.metadata
        prompt = JUDGE_TEMPLATE.format(
            question=md["question"],
            context=md["context"],
            answer=state.output.completion,
            expected_facts="\n".join(f"- {f}" for f in md["expected_facts"]),
        )
        out = await model.generate(prompt)
        judge = parse_judge_output(out.completion)
        if judge is None:
            return Score(value=0.0, answer=state.output.completion[:200],
                         metadata={"judge_ok": False, "groundedness": None,
                                   "goal_completion": None, "facts_satisfied": None})
        return Score(
            value=facts_fraction(judge),
            answer=state.output.completion[:200],
            metadata={
                "judge_ok": True,
                "groundedness": _dim_score(judge, "groundedness"),
                "goal_completion": _dim_score(judge, "goal_completion"),
                "facts_satisfied": (judge.get("factfulness") or {}).get("facts_satisfied"),
            },
        )

    return score
