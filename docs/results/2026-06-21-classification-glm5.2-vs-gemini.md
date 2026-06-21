# Classification benchmark — GLM 5.2 vs Gemini 2.5 Pro (2026-06-21)

First real `atsbench` run. Workflow: **document classification** of JSE regulatory filings.
Logs are gitignored; this file is the durable record.

## Setup

- **Task:** classify each filing on 6 fields (`is_financial`, `document_type`, `company`, `symbol`, `year`, `audited`) from the first ~3 pages of extracted text, using the team's verbatim production prompt.
- **Dataset:** 70 documents (35 financial / 35 not), labels derived from the team's filenames. 29 scanned/image PDFs excluded (no extractable text — out of scope for text-input v1).
- **Scoring:** per-field, mirroring `jse-doc-workflows/calculate_metrics.py`; headline = macro per-field accuracy. `year` scored only on financial docs; `company` uses lenient matching (see Caveats).
- **Routing:** OpenRouter, reasoning enabled, temperature 0. Cost computed from token usage × OpenRouter pricing.
- **Gate (anchored to the Gemini incumbent):** min_accuracy 0.90, max_latency 45 s, max_cost $0.03/doc.

## Result

| Rank | Model | Accuracy | p50 | p95 | $/doc | Gate | Pareto |
|---|---|---|---|---|---|---|---|
| 1 | **GLM 5.2** (`z-ai/glm-5.2`) | 0.936 ±.028 | **9.2 s** | **24.5 s** | **$0.0080** | pass | ★ |
| 2 | Gemini 2.5 Pro (`google/gemini-2.5-pro`) | 0.948 ±.025 | 16.9 s | 41.2 s | $0.0241 | pass | ★ |

### Per-field accuracy

| Field | GLM 5.2 | Gemini 2.5 Pro |
|---|---|---|
| is_financial | **1.00** | 0.97 |
| document_type | 0.94 | 0.94 |
| company | 0.98 | 0.98 |
| symbol | 0.98 | 0.98 |
| year (FS only) | 1.00 | 1.00 |
| audited (FS only) | 1.00 | 1.00 |
| exact-record | 0.73 | 0.71 |
| format-failures | 3 / 70 | 2 / 70 |

## Verdict

**For document classification, GLM 5.2 is the better buy.** Per-field, the two models are
indistinguishable — GLM is actually *ahead* on `is_financial` and tied on everything else.
Gemini's 1.2-point overall edge is entirely its one fewer JSON format-failure, not classification
skill. GLM delivers that same quality at **~2× the speed and ~1/3 the cost**. Both clear the gate;
both are Pareto-optimal only because Gemini's tiny accuracy lead is technically non-dominated — but
that lead is within the error bars, so in practice GLM wins.

If you adopt GLM 5.2 for this workflow, the one thing to add is **structured-output enforcement** to
eliminate the occasional unparseable-JSON answer (3/70 here).

## Caveats (about the benchmark, not the models)

- **`company` uses lenient matching.** The filename-derived golden abbreviates (`ltd` vs `limited`),
  expands parentheticals (`(ja)` vs `(jamaica)`), and carries cruft (`(jmd)`, `financial`,
  `renamed to…`). With strict matching, both models scored ~0.76 *despite producing correct legal
  names*; investigation confirmed it was a ground-truth artifact. The scorer now drops legal-form
  suffixes, strips parentheticals, and allows a ≥2-token subset. Verified against every mismatch in
  this run; one genuine difference (Mayberry Group vs Mayberry Investments) correctly remains a miss.
- **Symbols** were derived from the dataset filenames (the production JSE symbol DynamoDB needs AWS
  creds). All symbols in this dataset are covered.
- **29 of 99 documents** are scanned/image PDFs, excluded from the text-input benchmark.

## Spend

~$2.4 total (Gemini ~$1.68, GLM ~$0.56, plus a 5-doc profiling pass). Trivial.

## Reproduce

```bash
export OPENROUTER_API_KEY=...   # from .env
inspect eval src/atsbench/tasks/classification.py --model openrouter/google/gemini-2.5-pro \
  -M reasoning_enabled=true --temperature 0 --log-dir logs/run
inspect eval src/atsbench/tasks/classification.py --model openrouter/z-ai/glm-5.2 \
  -M reasoning_enabled=true --temperature 0 --log-dir logs/run
atsbench report --logs logs/run --workflow classification
```
