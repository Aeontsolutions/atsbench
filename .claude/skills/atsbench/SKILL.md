---
name: atsbench
description: Use when working in the atsbench LLM benchmarking repo and needing to run evals, generate scorecards, or add models — covers the inspect eval → atsbench report operational loop.
---

# atsbench

LLM benchmarking harness for JSE workflows. Models run via OpenRouter through Inspect AI; `atsbench report` aggregates logs into a gated scorecard.

## Environment setup

```bash
source .venv/bin/activate          # always activate first
# OPENROUTER_API_KEY must be in .env (loaded automatically by python-dotenv)
```

## Run an eval

```bash
inspect eval src/atsbench/tasks/<task>.py \
  --model openrouter/<vendor/slug> \
  -M reasoning_enabled=true \
  --temperature 0 \
  --log-dir logs/<dir>
```

| Task | File | Log dir |
|---|---|---|
| Document classification | `tasks/classification.py` | `logs/run/` |
| RAG Q&A | `tasks/rag_qa.py` | `logs/rag/` |
| Smoke (CI, mockllm) | `tasks/smoke.py` | `logs/smoke/` |

Run all candidate models into the **same** log dir before generating the report.

## Generate a report

```bash
atsbench report --logs logs/run --workflow classification
# workflows: classification | rag_qa | smoke
```

Prints ranked Markdown to stdout. Add `--json out.json` to also write machine-readable output.

## Scorecard columns

| Column | Meaning |
|---|---|
| Accuracy | Headline metric — per-field macro (classification) or factfulness fraction (RAG Q&A) |
| p50 / p95 | Latency percentiles across samples |
| $/sample | token usage × `models.yaml` pricing; judge tokens excluded |
| Gate | `pass` if model clears all thresholds in `workflows.yaml` |
| Pareto | ★ = not dominated by any other model on all axes simultaneously |

Ranking order: `primary_axis` in `workflows.yaml` (default: `cost`).

## Add a model

Edit `models.yaml`:

```yaml
- name: display-name
  provider: openrouter/vendor/slug
  price_per_1m_input: 1.25
  price_per_1m_output: 10.0
  trusted: true   # false = keep sensitive fixtures away from this model
```

## Key file locations

| File | Purpose |
|---|---|
| `models.yaml` | Model registry and pricing |
| `workflows.yaml` | Gate thresholds per workflow |
| `fixtures/classification/` | 70-doc JSE classification dataset |
| `fixtures/rag_qa/` | 13-record grounded Q&A dataset |
| `docs/results/` | Durable write-ups from past runs |
| `logs/` | Gitignored eval logs |
