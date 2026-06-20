# atsbench — Slice ② Document Classification Workflow Design

**Date:** 2026-06-21
**Status:** Approved (design) — pending spec review
**Builds on:** the slice-① core harness (`docs/superpowers/plans/2026-06-21-atsbench-core-harness.md`) and the overall design (`docs/superpowers/specs/2026-06-21-atsbench-benchmarking-harness-design.md`).

## Why classification first (premise correction)

The overall spec assumed *financial extraction* was the strongest first anchor because golden data existed. Investigation of `Aeontsolutions/jse-doc-workflows` found the opposite:

- `golden_dataset_documents/` holds **99 source PDFs but no committed extracted-value ground truth**. The extraction step has the production prompt but **zero golden figures** to grade against — objective extraction scoring would require building a human-verified golden set first.
- **Classification** has a real, committed signal: the team's **filenames encode the labels**, e.g. `barita_investments_limited-BIL-audited_financial_statements-year_ended_september-30-2023.pdf`. Their existing scorer `scripts/calculate_metrics.py` defines the exact notion of correctness.

So classification is the first real slice: objective, ground-truth-backed from committed data, no S3 or human annotation needed.

## Decisions (settled during brainstorming)

1. **Workflow:** document classification (promoted ahead of extraction).
2. **Ground truth:** derived from the committed filenames — fields `is_financial`, `document_type`, `company`, `symbol`, `year`, `audited`.
3. **Frozen model input:** extracted text of the **first ~3 pages** of each PDF (universal across text models, cheap, deterministic; classification signal lives on the cover pages). Every model sees identical frozen text.
4. **`document_type` taxonomy (5 canonical classes)**, from the team's sampling config: `audited_financial_statements`, `unaudited_financial_statements`, `annual_report`, `prospectus`, `other`.
5. **Scorer mirrors `calculate_metrics.py`** per field (see Scoring).
6. **Headline accuracy = macro mean of per-field accuracy** (gate uses this); scorecard also shows **exact-record** accuracy and the per-field breakdown.
7. **Corpus is published JSE filings (public)** — low data-sensitivity; the trusted/exclude-sensitive gate barely binds, but fixtures still carry a sensitivity tag.
8. **Tier-2 deferred:** `period_end` exact, statement-presence flags, page-localization IoU require the S3 `golden_evaluation_dataset.json`; the scorer is designed to extend into them without rework.

## Architecture

Reuses the slice-① core unchanged (providers/registry, gate→Pareto→rank report, renderers, CLI). New units only:

```
fixtures/classification/
  build_fixtures.py     # one-time prep: PDFs -> dataset.jsonl (run locally, not in CI)
  dataset.jsonl         # 99 committed records: {id, input_text, golden{...}, source_filename, sensitivity}
  MANIFEST.md           # provenance + per-record content hash
src/atsbench/
  fixtures/filename_labels.py   # parse a golden filename -> labels (pure, heavily tested)
  scorers/classification.py     # per-field matching (pure) + thin @scorer adapter
  tasks/classification.py       # Inspect Task: dataset + prod-prompt solver + scorer
workflows.yaml          # add a `classification` workflow + gate
```

### Fixture pipeline (one-time prep → small committed artifacts)

`build_fixtures.py` reads the 99 PDFs from a local checkout of `jse-doc-workflows/golden_dataset_documents/` and for each:

1. **Parse the filename → golden labels** via `filename_labels.parse_filename(name)`. Pattern is roughly `{company}-{SYMBOL}-{document_type}_{date}` with `_`/`-` separator drift, leading underscores, `(formerly X)` parentheticals, and `&` in names. Unparseable filenames are **flagged and excluded with a logged reason — never silently mislabeled.**
2. **Extract first ~3 pages of text** (pypdf/pdfplumber), normalized whitespace, as the frozen `input_text`.
3. Emit a record: `{id, input_text, golden:{is_financial, document_type, company, symbol, year, audited}, source_filename, sensitivity:"public"}`.

Output: `dataset.jsonl` (text + labels — small, committed) and `MANIFEST.md` (counts, any excluded files, content hashes). The **PDFs are not committed** — they are fetched once locally for prep.

### Task + scorer

- `tasks/classification.py` — loads `dataset.jsonl` as Inspect `Sample`s (`input=input_text`, `metadata=golden`), solver applies the **verbatim production classification prompt** (harvested from the repo during build), single generation; the model returns its classification JSON.
- `scorers/classification.py` — pure per-field comparison, then a thin `@scorer` adapter (the slice-① template). Inspect dict-valued `Score` with per-field metrics + the headline.

## Scoring (mirrors `calculate_metrics.py`)

Per field, per document:

| Field | Rule |
|---|---|
| `is_financial` | boolean exact |
| `audited` | boolean exact |
| `document_type` | canonical exact (after mapping to the 5 classes) |
| `company` | normalized exact — uppercase, `&`→`AND`, strip all punctuation, collapse whitespace, trim |
| `symbol` | case-insensitive exact |
| `year` | string exact (`str(gt) == str(pred)`) |

- **Headline `accuracy`** (gate axis) = mean over fields of per-field correctness, averaged over documents (macro per-field).
- **Secondary:** exact-record accuracy (all six fields correct) + per-field accuracy breakdown, surfaced in the scorecard.
- **Format failure:** model output that doesn't parse as the expected JSON scores 0 for that document and is counted in the format-failure rate (never crashes the run).
- Cost/latency/token axes come for free from the slice-① aggregator.

## Error handling & robustness

- Filename parser flags-and-excludes rather than mislabels; the MANIFEST records every exclusion.
- Bad model JSON → scored-0 format-failure, surfaced in the report.
- Fixtures frozen + content-hashed for cross-run comparability; `input_text` is deterministic (fixed page count + whitespace normalization).
- Temperature 0 where supported.

## Testing

- **Filename parser (highest-risk):** TDD against real examples and the known edge cases — leading underscore (`_mayberry_group_ltd.-MGL-…`), `(formerly icreate limited)`, `&` (`amg_packaging_&_paper…`), `_` vs `-` separators, missing/lowercase symbols, date-only tails (`…_dolla_annual_report_2022`). Includes an "unparseable → flagged" case.
- **Scorer:** unit tests per field, especially `company` normalization (the team's exact rule) and `document_type` mapping.
- **End-to-end:** a tiny smoke fixture + `mockllm` run proving the classification task → scorecard loop at zero cost (same pattern as slice ①'s `test_end_to_end`).

## One-time build dependencies (resolved during planning/build, grounded in the repo — not guessed)

- Fetch the 99 PDFs once: a shallow/sparse checkout of `jse-doc-workflows` `golden_dataset_documents/` (≈ hundreds of MB; local only, not committed).
- Harvest from the repo: the **verbatim classification prompt**, the model's **allowed `document_type` values**, and the team's **`is_financial` definition** (e.g. whether `prospectus`/`annual_report` count as financial). The filename-token → canonical-type map is finalized against these.

## Open items (pinned at build time)

- Exact `is_financial` definition per the harvested prompt (does `prospectus` or a bare `annual_report` count?).
- The filename-token → canonical-`document_type` map (enumerated from the actual 99 filenames).
- Verbatim production classification prompt text.
- Number of pages to freeze (default 3; confirm signal coverage on a sample).
- Tier-2 fields await the S3 `golden_evaluation_dataset.json`.
