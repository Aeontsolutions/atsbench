# atsbench — Workflow Benchmarking Harness Design

**Date:** 2026-06-21
**Status:** Approved (design) — pending spec review
**Author:** Elroy Galbraith (with Claude)

## Problem

When a new model ships (e.g. GLM 5.2), we can only judge it by its publicized
benchmarks, which don't reflect the work we actually use LLMs for. We need a
repeatable harness that scores **any new model** against **Aeontsolutions' real
workflows**, producing a comparable accuracy / cost / latency answer versus our
current incumbents (mostly Google Gemini today).

## Goals

- Evaluate any new model on demand with minimal effort ("add a model = one config line").
- Cover the four workflows that represent what we need LLMs for.
- Produce trustworthy, reproducible, comparable scores — not vibes.
- Score every model on three co-equal axes — **accurate, fast, affordable** — and
  resolve them into a clear per-workflow verdict (gate + ranked scorecard).
- Keep sensitive regulatory filings under data-governance control.

## Non-Goals

- Running the full production pipelines end-to-end (AWS Step Functions, Textract,
  live BigQuery). We benchmark the **isolated model call** on frozen fixtures.
- Replacing production observability or LangSmith tracing.
- Red-teaming / safety evaluation (out of scope for v1).

## Core Decisions (settled during brainstorming)

1. **Coverage:** all four workflows as plugin tasks — financial extraction, RAG
   chatbot Q&A, document classification, text-to-SQL.
2. **Test boundary:** isolated LLM call on **frozen fixtures**. Every model sees
   identical inputs (including frozen RAG context), so we isolate model quality
   from pipeline quality.
3. **Open-ended scoring:** neutral **LLM-as-judge + reference answers** for RAG
   Q&A; objective scorers everywhere else.
4. **Model routing:** **LiteLLM-style gateway with BYO keys**, realized natively
   by the Inspect AI provider layer; runs locally, no third-party hop by default.
5. **Substrate:** build on **Inspect AI** (UK AISI). We write only fixtures, four
   scorers, and a report aggregator; Inspect provides providers, retries, logging,
   parallelism, and a viewer.

## Architecture

A small reusable core, four workflow tasks as plugins, and a report aggregator.

```
src/atsbench/
  providers.py          # model registry: friendly-name -> provider/model/base_url/pricing; keys from env
  tasks/                # one Inspect Task each: dataset(frozen fixtures) + solver(prod prompt) + scorer
    financial_extraction.py
    doc_classification.py
    rag_qa.py
    text_to_sql.py
  scorers/              # field_match | label_match | sql_exec_match | judge  (TDD'd — bug-prone core)
  report/               # aggregate .eval logs across models -> leaderboard (md/json) + Inspect View
  cli.py                # atsbench run --task X --model Y | compare --models a,b,c | report
fixtures/               # frozen inputs + golden outputs, content-hashed in MANIFEST.md (provenance + sensitivity)
models.yaml             # the registry edited to add new models (e.g. GLM 5.2)
workflows.yaml          # per-workflow gates: accuracy floor + max latency/$ budgets + primary axis
tests/                  # scorer unit tests + mock provider for zero-cost end-to-end CI
```

### Component responsibilities

- **providers.py / models.yaml** — maps a friendly model name to an Inspect model
  string (native provider) or an OpenAI-compatible `base_url` + pricing metadata.
  Adding a model is a config edit. Reads API keys from the environment.
- **tasks/** — each task is an Inspect `Task` = a dataset of frozen fixtures, a
  solver that applies the **verbatim production prompt** as a single generation
  step, and a task-specific scorer. Tasks are independent and share nothing but
  the core.
- **scorers/** — the part most likely to be subtly wrong, so it is unit-tested
  first (TDD). Pure functions over (model output, gold) → score + metadata.
- **report/** — reads Inspect's structured `.eval` logs across models, applies each
  workflow's gate, ranks survivors by the primary axis, and renders a three-axis
  scorecard with the Pareto set highlighted (markdown + JSON); Inspect View provides
  per-sample drill-down.
- **cli.py** — thin wrapper: `run`, `compare`, `report`.

### Data flow (per run)

1. `atsbench run --task financial_extraction --model glm-5.2`
2. Load frozen fixtures (inputs + gold) as an Inspect dataset.
3. Solver applies the verbatim production prompt to each input → single model
   generation through Inspect's provider layer (resolved via the registry).
4. Task scorer produces per-sample score + metadata (judge confidence for RAG).
5. Inspect writes a structured `.eval` log (I/O, scores, token usage, timing).
6. `atsbench report` aggregates logs across models into the leaderboard.

## Scoring

| Task | Scorer | Metric |
|---|---|---|
| Financial extraction | `field_match` — parse JSON, type-aware per-field match: numbers within relative tolerance + scale handling (thousands/millions), strings normalized (whitespace/case/currency) | field precision/recall/F1, exact-record accuracy, JSON-validity rate |
| Doc classification | `label_match` — predicted vs gold label | macro-F1 + per-class confusion |
| Text-to-SQL | `sql_exec_match` — execute candidate SQL on a local **DuckDB** fixture, compare result sets order-insensitively (type-normalized); error/empty → fail | result-set exact-match rate |
| RAG Q&A | `judge` — neutral LLM-as-judge with a rubric (faithfulness-to-context, correctness-vs-reference, completeness); judge model **fixed and excluded from the candidate pool**; low-confidence / judge-vs-reference disagreement auto-flagged to a review queue | rubric score + flagged-for-review count |

### The three scoring axes (co-equal)

Every workflow scores a model on three co-equal axes — not accuracy with footnotes:

- **Accurate** — the task scorer above (field-F1 / macro-F1 / result-set match /
  judge rubric), plus JSON-validity, format-failure, and refusal rates.
- **Fast** — latency per sample, reported p50/p95.
- **Affordable** — $ cost per sample (from registry pricing), plus $/correct.

### Verdict — gates + ranked scorecard

Each workflow declares a **gate** and a **primary axis**:

- **Gate** — a minimum accuracy floor plus optional max-latency and max-$ budgets.
  A model that fails the gate is disqualified for that workflow, so a cheap-but-wrong
  or slow-but-right model cannot win on a technicality.
- **Rank** — models that clear the gate are ranked by the workflow's primary axis
  (e.g. cost) in a three-axis scorecard.
- **Pareto highlight** — the non-dominated set (models you can't make more accurate,
  faster, or cheaper without giving up another axis) is flagged, so the trade-off
  stays visible after ranking.

Gates are **per-workflow**: a real-time chatbot's latency budget is not a batch
extractor's. Budgets are **anchored to the incumbent** — the current Gemini model is
benchmarked first to set the baseline that "fast" and "affordable" are measured
against, so the thresholds are concrete rather than arbitrary.

## Data Governance

Fixtures are JSE regulatory filings, some sensitive. Each fixture carries a
sensitivity tag. A provider allowlist plus `--exclude-sensitive` guarantees
embargoed/sensitive documents are never shipped to providers we don't trust
(e.g. Zhipu/OpenRouter). Each run's manifest records exactly what data went to
which provider (data-egress audit trail).

## Robustness & Error Handling

- Temperature 0 where supported; record model version/snapshot id per run.
- Fixtures frozen and content-hashed in `MANIFEST.md` for cross-run comparability.
- Malformed model output (bad JSON) = scored-0 **format-failure**, surfaced in the
  report — never crashes a run.
- Provider/network errors use Inspect's retry/backoff; errored samples are counted
  in the report, **never silently dropped**.
- Cost guardrails: `--limit N` sample cap and a pre-run token/$ estimate.
- Judge-bias control: judge fixed and excluded from candidates; periodic human
  calibration sample.

## Testing

- Unit tests for every scorer (numeric tolerance, set comparison, judge parsing) —
  written first (TDD).
- A tiny smoke fixture set + a **mock/echo provider** so the whole harness runs
  end-to-end in CI with no API calls and no cost.
- Golden-scorer tests: known (input, output) pairs with expected scores.

## Fixtures to Harvest (not built from zero)

- `jse-doc-workflows/golden_dataset_documents` + its production extraction and
  classification prompts → financial extraction + classification fixtures.
- `jse-datasphere-chatbot/evals/` → RAG Q&A fixtures, reference answers, and the
  production RAG prompt; freeze the retrieved context per question.
- `ats-llm-eval/test_docs` + `jacie_benchmark.ipynb` → additional cases.
- **Text-to-SQL** is the one gap: snapshot a slice of the BigQuery schema + data
  into a DuckDB fixture and assemble a question set with expected result rows.
  This fixture set requires Elroy's input and is scheduled with task ⑤.

## Build Order (each slice independently shippable)

1. **Core** — providers/registry, Inspect task scaffolding, report aggregator,
   mock provider, scorer test harness.
2. **Financial extraction** — end-to-end on 2–3 real models incl. a GLM (proves
   the full loop + report). Objective scoring, golden data already exists.
3. **Doc classification** — second objective task, reuses everything.
4. **RAG Q&A** — judge scorer + fixture harvest from `datasphere/evals`.
5. **Text-to-SQL** — DuckDB fixture + execution scorer (needs the fixture above).

## Open Items (resolved at implementation-planning time)

- Confirm package name `atsbench`.
- `git init` this directory (currently not a repo) — done as part of spec commit.
- Text-to-SQL fixture (schema snapshot + question set + expected rows) — needs
  Elroy's input during slice ⑤.
- Per-workflow gate values (accuracy floor, latency/$ budgets, primary axis) — set
  with Elroy after the incumbent Gemini baseline run in slice ②.
```
