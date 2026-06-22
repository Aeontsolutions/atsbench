# atsbench

Benchmark any LLM against Aeontsolutions' real JSE workflows on three axes: accuracy, latency, and cost.

Built on [Inspect AI](https://inspect.ai). Models run via [OpenRouter](https://openrouter.ai).

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- An OpenRouter API key

## Install

```bash
uv sync
source .venv/bin/activate
```

Install the Claude skill (one-time, per developer) so Claude Code can assist with running evals:

```bash
mkdir -p ~/.claude/skills && ln -s "$PWD/.claude/skills/atsbench" ~/.claude/skills/atsbench
```

Copy `.env.example` to `.env` and set your key:

```bash
OPENROUTER_API_KEY=sk-or-...
```

## Run an eval

Two tasks are available:

| Task | File | Log dir convention |
|---|---|---|
| Document classification | `src/atsbench/tasks/classification.py` | `logs/run/` |
| RAG Q&A | `src/atsbench/tasks/rag_qa.py` | `logs/rag/` |

```bash
inspect eval src/atsbench/tasks/classification.py \
  --model openrouter/google/gemini-2.5-pro \
  -M reasoning_enabled=true \
  --temperature 0 \
  --log-dir logs/run
```

Run a second model into the same log dir to compare them side-by-side in the report.

## Generate a report

```bash
atsbench report --logs logs/run --workflow classification
```

Available workflows: `classification`, `rag_qa`, `smoke`.

The report prints a ranked Markdown scorecard to stdout. To also write JSON:

```bash
atsbench report --logs logs/run --workflow classification --json out.json
```

## Add a model

Edit `models.yaml`:

```yaml
models:
  - name: my-model                        # display name used in reports
    provider: openrouter/vendor/slug       # Inspect model string
    price_per_1m_input: 1.25              # USD — set to OpenRouter pricing
    price_per_1m_output: 10.0
    trusted: true                          # false = keep sensitive fixtures away from this model
```

Provider slugs are on [openrouter.ai/models](https://openrouter.ai/models). For reproducible runs, pin the backend and forbid quantization via the `-M provider=...` flag (see comments in `models.yaml`).

## Interpret the scorecard

The scorecard ranks models and applies a **gate** defined in `workflows.yaml`:

| Column | Meaning |
|---|---|
| Accuracy | Headline metric (per-field macro for classification; factfulness fraction for RAG Q&A) |
| p50 / p95 | Latency percentiles across samples |
| $/sample | Cost from token usage × pricing in `models.yaml` (judge tokens excluded) |
| Gate | `pass` if the model clears all thresholds (`min_accuracy`, `max_latency_s`, `max_cost_per_sample_usd`) |
| Pareto | ★ = no other model beats this one on every axis simultaneously |

Models are ranked by `primary_axis` (default: `cost`). Gate thresholds are anchored to the Gemini 2.5 Pro baseline run — see `workflows.yaml` for the exact values.

Durable result write-ups live in `docs/results/`.
