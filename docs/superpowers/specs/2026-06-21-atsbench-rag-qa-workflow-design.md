# atsbench — Slice ③ RAG Q&A Workflow Design

**Date:** 2026-06-21
**Status:** Approved (design) — pending spec review
**Builds on:** the slice-① core, the classification slice, and the overall design.

## Why this shape (reality vs the original spec)

The overall spec assumed RAG Q&A would have "frozen retrieved context + reference answers + LLM-as-judge." Investigation of `Aeontsolutions/jse-datasphere-chatbot` found:

- `evals/` is **not a Q&A dataset** — it's a **persona-simulation** harness (a Gemini model role-plays a user, drives a *multi-turn* conversation against the *live, agentic* chatbot — router → BigQuery / S3 / web — and a Gemini 2.5 Pro judge scores the transcript on a 6-dimension rubric).
- There are **no golden questions or reference answers**; the closest signal is per-persona **`expected_facts`** (NL assertions, checked binary).
- Retrieval is live and agentic; the **financial/BigQuery path is the most freezable**.
- A complete LLM-as-judge already exists (`evals/judge.py`, `evals/config/judge_rubric.yaml`) — reusable.

This collides with our harness principle (*isolated model on frozen fixtures*). So we adopt **frozen isolated-generation**: freeze `(question + retrieved context + expected_facts)`, benchmark only the **answer-generation model**, judge with a neutral fixed model.

## Decisions (settled during brainstorming)

1. **Path:** the **financial** path only (most freezable). Document/web paths and the multi-turn persona-sim are out of scope for v1.
2. **Boundary:** **single-turn**, isolated generation — question + frozen context → answer. (The multi-turn persona-sim is a system-level eval, deliberately not this.)
3. **Fixtures:** **hand-built**, ~15–25 records, committed. Self-contained `context` snippets (J$ figures) grounded where possible in real figures from the 35 financial PDFs already in the classification dataset, then Elroy-verified. Includes a few **negative** (out-of-scope) cases.
4. **Prompt:** the **harvested production financial-synthesis prompt** verbatim (system "JSE Financial Analyst" + the data-context user turn).
5. **Scoring:** **LLM-as-judge** with a **neutral fixed** model (excluded from the candidate pool), using a 3-dimension subset of the team's rubric — **groundedness, factfulness, goal_completion**. **Headline accuracy = factfulness fraction** (expected_facts satisfied); groundedness + goal_completion are secondary; low groundedness flags a confidently-wrong answer.
6. **Judge model:** a neutral default (a Claude-class model via OpenRouter), held fixed across all candidates. Must not be a model under test.

## Architecture

Reuses the core unchanged (providers/registry, gate→Pareto→rank report, renderers, CLI). New units:

```
fixtures/rag_qa/
  dataset.jsonl     # ~15-25 hand-built records (committed)
  judge_prompt.txt  # harvested + adapted judge rubric/prompt (committed)
  system_prompt.txt # harvested production financial-synthesis prompt (committed)
  MANIFEST.md       # provenance + the "context supports expected_facts" check
src/atsbench/
  scorers/rag_qa.py # judge-call adapter + pure aggregation (the slice-① template, judge variant)
  tasks/rag_qa.py   # Inspect Task: dataset + prod-prompt solver + judge scorer
workflows.yaml      # add a `rag_qa` workflow + gate
```

### Fixture format

Each `dataset.jsonl` record:
```json
{
  "id": "ncb_revenue_2023",
  "question": "What was NCB Financial Group's total revenue for FY2023, and how did it compare to FY2022?",
  "context": "Financial data (J$'000):\nNCBFG | FY2023 | Total revenue | 145,200,000\nNCBFG | FY2022 | Total revenue | 132,800,000\n...",
  "expected_facts": [
    "States NCBFG FY2023 total revenue of ~J$145.2 billion",
    "Compares to FY2022 (~J$132.8 billion) or states the YoY change"
  ],
  "category": "positive"
}
```
Negative records carry an out-of-scope `question`, an empty/irrelevant `context`, and an `expected_facts` like *"Declines or redirects the out-of-scope request to JSE/financial topics."*

### Task + scorer

- `tasks/rag_qa.py` — loads the JSONL, solver applies the harvested system prompt + the financial-synthesis user turn (`Financial data retrieved…: {context}\n\nAnswer using ONLY this data. Use J$…`), single generation → free-form answer.
- `scorers/rag_qa.py` — a `@scorer` that calls the **neutral judge model** (via Inspect's `get_model`) with the harvested judge prompt (question + context + answer + expected_facts), parses the judge's JSON (`groundedness`, `factfulness.facts_satisfied[]`, `goal_completion`), and returns `Score(value=factfulness_fraction, metadata={groundedness, goal_completion, facts_satisfied, judge_ok})`. Pure helpers (`facts_fraction`, judge-JSON parse) are unit-tested; the judge call is the only model dependency.

## Scoring

- **Headline (gate axis) = factfulness fraction** = mean over fixtures of `(#expected_facts satisfied / #expected_facts)`, via Inspect's `mean()` metric (the aggregator already reads `accuracy`→`mean`).
- **Secondary:** mean groundedness (1–5) and mean goal_completion (1–5), surfaced in metadata; a low-groundedness/high-factfulness answer is flagged (hallucinated-but-lucky).
- **Judge failure** (judge output unparseable) → that sample flagged `judge_ok=False` and excluded-or-zeroed (counted, never silently dropped); surfaced in the report.
- Cost/latency/token axes come from the slice-① aggregator — note these reflect the **candidate's** generation only; the judge's own tokens are tracked separately and reported as judging overhead, not charged to the candidate.

## Error handling & robustness

- Judge held fixed + excluded from candidates (no self-preference); judge temperature low for stability.
- Unparseable candidate answer or judge output → flagged + counted, never crashes.
- Fixtures frozen + content-hashed; each `context` must support its `expected_facts` (validated at build).
- Temperature 0 for candidates where supported.

## Testing

- **Judge scorer with a mock judge:** a deterministic stub judge output verifies the parse + factfulness-fraction collapse at zero cost.
- **Pure aggregation** (`facts_fraction`, judge-JSON parsing) unit-tested.
- **End-to-end:** mock candidate + mock judge → scorecard loop at zero cost (slice-① e2e pattern).
- **Fixture validity test:** every record's `expected_facts` are answerable from its `context` (a structural check, plus Elroy's verification).

## Build dependencies (harvested verbatim, grounded in the repo)

- The production **financial-synthesis system prompt** + user-turn template (`agent_v2.py`).
- The **judge rubric + judge prompt** (`evals/judge.py`, `evals/config/judge_rubric.yaml`) — adapt to the single-turn 3-dimension subset.
- Real financial figures for grounding the fixtures (from the financial PDFs in `fixtures/classification/` source set or the documents themselves).

## Open items

- Confirm the neutral **judge model** OpenRouter slug (default: a Claude-class model; must not be a candidate).
- Finalize the ~15–25 fixtures with Elroy's verification of the financial figures + expected_facts.
- Deferred: document/web retrieval paths, multi-turn persona-sim (system-level eval), and scaling fixtures via live BigQuery/chatbot capture.
