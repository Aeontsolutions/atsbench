# atsbench Slice ③ — RAG Q&A Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a RAG Q&A benchmark that scores any model's *answer generation* on frozen `(question + financial context + expected_facts)` fixtures, graded by a neutral LLM-as-judge against the expected facts.

**Architecture:** Reuses the slice-① core. New units: a hand-built fixture set (controller-drafted, Elroy-verified), an Inspect task applying the harvested production financial-synthesis prompt single-turn, and a **judge-based scorer** that calls a fixed neutral judge model and collapses its verdict to a factfulness-fraction headline. The judge call is the only new pattern (a model-graded scorer); its pure parts (judge-JSON parse, fact aggregation) are unit-tested and the judge call is exercised end-to-end with a mock judge.

**Tech Stack:** Python 3.11+, Inspect AI, pytest. Same uv environment as slices ①–②.

## Global Constraints

- **Frozen isolated single-turn generation:** question + frozen context → answer. No live retrieval, no multi-turn.
- **Financial path only.** Document/web paths and the persona-sim are out of scope.
- **Headline accuracy = factfulness fraction** (`#expected_facts satisfied / #expected_facts`), surfaced via Inspect `mean()` (the aggregator already reads `accuracy`→`mean`).
- **Judge = a fixed neutral model, excluded from the candidate pool** (default `openrouter/anthropic/claude-3.7-sonnet` — confirm slug). Judge tokens are judging overhead, not charged to the candidate.
- **Prompts harvested verbatim:** the financial-synthesis system prompt from `agent_v2.py`; the judge rubric is adapted (3-dimension subset) from `evals/judge.py` + `judge_rubric.yaml`.
- Bad candidate answer or unparseable judge output → flagged + counted, never crashes (scored 0 / `judge_ok=False`).
- Scorer = pure logic + thin adapter (the slice-① template, judge variant). YAGNI.

---

### Task 1: RAG fixtures (controller-drafted, Elroy-verified) + smoke fixture

> **This task is handled by the controller (me), not a subagent** — it requires drafting financial figures grounded in real statements and a human verification loop. The subagent code tasks below depend only on the committed *smoke* fixture, so they can proceed in parallel with fixture verification.

**Files:**
- Create: `fixtures/rag_qa/dataset.jsonl` (~15–25 records, Elroy-verified)
- Create: `fixtures/rag_qa/MANIFEST.md` (provenance + the "context supports expected_facts" check)
- Create: `tests/fixtures/rag_qa_smoke.jsonl` (3 records, for the e2e)

**Record format** (one JSON object per line):
```json
{"id": "ncb_revenue_2023", "question": "What was NCB Financial Group's total revenue for FY2023, and how did it compare to FY2022?", "context": "Financial data (J$'000):\nNCBFG | FY2023 | Total revenue | 145,200,000\nNCBFG | FY2022 | Total revenue | 132,800,000", "expected_facts": ["States NCBFG FY2023 total revenue (~J$145.2bn)", "Compares to FY2022 (~J$132.8bn) or gives the YoY change"], "category": "positive", "sensitivity": "public"}
```
- `category` is `positive` or `negative`. Negative records carry an out-of-scope `question`, an empty `context`, and an `expected_facts` like `["Declines or redirects the out-of-scope request to JSE/financial topics"]`.
- **Validity rule** (verified at build + by Elroy): every `expected_fact` must be answerable from that record's `context`.

**Steps (controller):**
- [ ] Draft ~15–25 records grounded in real figures pulled from the financial statements in the classification source set (3–5 negative cases included). Write `dataset.jsonl` + `MANIFEST.md`.
- [ ] Present the drafted fixtures to Elroy; correct figures/expected_facts per his verification.
- [ ] Write `tests/fixtures/rag_qa_smoke.jsonl` (3 hand-written records: a positive financial Q, a comparison Q, a negative out-of-scope Q).
- [ ] Commit the verified fixtures.

---

### Task 2: Judge scorer

**Files:**
- Create: `src/atsbench/scorers/rag_qa.py`
- Test: `tests/test_rag_qa_scorer.py`

**Interfaces:**
- Consumes: Inspect `get_model`/`Model`, `Score`/`Target`/`TaskState`/`mean`/`stderr`.
- Produces:
  - `parse_judge_output(raw: str) -> dict | None` — extract JSON from the judge's text (first `{` to last `}`), `None` on failure.
  - `facts_fraction(judge: dict) -> float` — `#true / #facts` from `judge["factfulness"]["facts_satisfied"]`; `0.0` if empty/missing.
  - `JUDGE_TEMPLATE: str`, `DEFAULT_JUDGE: str`.
  - `rag_qa_judge(judge_model: str | Model = DEFAULT_JUDGE)` — an Inspect `@scorer(metrics=[mean(), stderr()])`; `Score.value` = factfulness fraction; metadata carries `judge_ok`, `groundedness`, `goal_completion`, `facts_satisfied`.

- [ ] **Step 1: Write the failing test (pure parts)**

`tests/test_rag_qa_scorer.py`:
```python
from atsbench.scorers.rag_qa import facts_fraction, parse_judge_output


def test_facts_fraction():
    assert facts_fraction({"factfulness": {"facts_satisfied": [True, True, False]}}) == 2 / 3
    assert facts_fraction({"factfulness": {"facts_satisfied": []}}) == 0.0
    assert facts_fraction({}) == 0.0
    assert facts_fraction({"factfulness": {"facts_satisfied": [True, True]}}) == 1.0


def test_parse_judge_output():
    assert parse_judge_output('Here: {"factfulness": {"facts_satisfied": [true]}} done') == \
        {"factfulness": {"facts_satisfied": [True]}}
    assert parse_judge_output("no json at all") is None
```

- [ ] **Step 2: Run it; verify it fails**

Run: `uv run pytest tests/test_rag_qa_scorer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'atsbench.scorers.rag_qa'`.

- [ ] **Step 3: Write `src/atsbench/scorers/rag_qa.py`**

```python
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
                         metadata={"judge_ok": False})
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
```

- [ ] **Step 4: Run it; verify it passes**

Run: `uv run pytest tests/test_rag_qa_scorer.py -v`
Expected: PASS (2 passed). If `Model`/`get_model` import paths differ in the installed Inspect, run `uv run python -c "import inspect_ai.model as m; print('get_model' in dir(m), 'Model' in dir(m))"` and adjust the import; keep the pure functions unchanged.

- [ ] **Step 5: Commit**

```bash
git add src/atsbench/scorers/rag_qa.py tests/test_rag_qa_scorer.py
git commit -m "feat: RAG Q&A judge scorer (factfulness fraction via neutral judge)"
```

---

### Task 3: RAG task, harvested prompts, gate, and end-to-end smoke

**Files:**
- Create: `src/atsbench/tasks/rag_qa.py`
- Create: `fixtures/rag_qa/system_prompt.txt` (fetched verbatim)
- Modify: `workflows.yaml` (add `rag_qa`)
- Test: `tests/test_rag_qa_task.py`

**Interfaces:**
- Consumes: `rag_qa_judge` (Task 2); the dataset record format (Task 1); `load_workflows` (slice ①).
- Produces: `load_dataset(path) -> list[Sample]`, `rag_qa_task(dataset_path=None, judge_model=...) -> Task`, `USER_TEMPLATE`.

- [ ] **Step 1: Fetch the production financial-synthesis system prompt**

```bash
gh api repos/Aeontsolutions/jse-datasphere-chatbot/contents/fastapi_app/agent_v2.py --jq .content | base64 -d > /tmp/agent_v2.py
```
Find the `SYSTEM_PROMPT` string constant (the "JSE Financial Analyst" identity + safety/scope/style rules) and write its exact value to `fixtures/rag_qa/system_prompt.txt`. Copy verbatim; do not paraphrase. (If the path differs, locate it: `gh api repos/Aeontsolutions/jse-datasphere-chatbot/git/trees/HEAD?recursive=1 --jq '.tree[].path' | grep -i agent_v2`.)

- [ ] **Step 2: Write the failing test**

`tests/test_rag_qa_task.py`:
```python
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
```
(The smoke fixture has records whose `expected_facts` lists are length 2, matching the mock judge's two `facts_satisfied` booleans; if a smoke record has a different count, give it 2 expected_facts or adjust the mock judge output to match that record's count.)

- [ ] **Step 3: Run it; verify it fails**

Run: `uv run pytest tests/test_rag_qa_task.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'atsbench.tasks.rag_qa'`.

- [ ] **Step 4: Write `src/atsbench/tasks/rag_qa.py`**

```python
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
```

- [ ] **Step 5: Add the `rag_qa` workflow to `workflows.yaml`**

Append under `workflows:`:
```yaml
  - name: rag_qa
    gate:
      min_accuracy: 0.7          # factfulness floor; re-anchor to the Gemini baseline after the first run
      primary_axis: cost
```

- [ ] **Step 6: Run the test**

Run: `uv run pytest tests/test_rag_qa_task.py -v`
Expected: PASS (2 passed), no network (both candidate and judge are `mockllm`). If `system_message`/`generate` or `eval` kwargs differ, mirror the working forms already in `src/atsbench/tasks/classification.py` and re-run.

- [ ] **Step 7: Commit**

```bash
git add src/atsbench/tasks/rag_qa.py fixtures/rag_qa/system_prompt.txt workflows.yaml tests/test_rag_qa_task.py
git commit -m "feat: RAG Q&A task, harvested synthesis prompt, gate, mock-judge e2e"
```

---

## Self-Review

**Spec coverage:**
- Frozen single-turn isolated generation → Task 3 `USER_TEMPLATE` + solver. ✓
- Financial path only → fixtures + synthesis prompt. ✓
- Hand-built fixtures (question + context + expected_facts + negatives), Elroy-verified, context-supports-facts validity → Task 1. ✓
- Harvested production synthesis system prompt → Task 3 Step 1. ✓
- LLM-as-judge, neutral fixed model excluded from candidates, 3-dim subset → Task 2 (`JUDGE_TEMPLATE`, `rag_qa_judge`). ✓
- Headline = factfulness fraction via `mean()` → Task 2 (`Score.value = facts_fraction`). ✓
- Judge failure flagged + counted, never crashes → Task 2 (`judge_ok=False`, value 0). ✓
- Plugs into core report/CLI + `rag_qa` gate → Task 3. ✓
- Mock-judge tests at zero cost → Task 2 unit + Task 3 e2e. ✓

**Deferred (own later work):** document/web retrieval paths, multi-turn persona-sim, scaling fixtures via live BigQuery/chatbot capture, re-anchoring the gate from a real baseline, surfacing groundedness/goal_completion + judging-overhead cost as report columns (currently in Score metadata / tracked separately).

**Placeholder scan:** none. `DEFAULT_JUDGE` slug + the fixture figures are data to confirm/verify (flagged), not code placeholders.

**Type consistency:** dataset record keys (`question, context, expected_facts, category`) are identical across Task 1 format, Task 3 `load_dataset`/metadata, and Task 2 scorer reads. `rag_qa_judge(judge_model)` signature consistent between Task 2 (def) and Task 3 (call). `Score.value` float consumed by the slice-① `mean`-aware aggregator. ✓
