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
4. **`document_type` = the production model's 29-value enum** (harvested verbatim from `CLASSIFICATION_SYSTEM_PROMPT`): `audited_financial_statements`, `unaudited_financial_statements`, `annual_report`, `prospectus`, `general_meetings`, `other_company_news`, `acquisitions_mergers_and_disposals`, `management_appointments_resignations_and_retirements`, `jse_event_news`, `director_appointments_resignations_and_retirements`, `trading_in_shares`, `dividend_declaration`, `nav`, `bulletin`, `takeover_bids_and_scheme_of_arrangements`, `dividend_consideration`, `rights_issue`, `jse_education_news`, `jse_trading_news`, `jse_monthly_regulatory_report`, `basis_of_allotment`, `disclosure_of_shareholders`, `committee_news`, `performance_report`, `corporate_governance_policy_and_guidelines`, `share_buy_back`, `stock_split`, `articles`, `directors_circular`, `delisting_notice`. (My earlier "5 classes" was the sampling config, not the label space — corrected.) Golden labels map each filename's type-token into this enum: **mostly identity**, with special cases `quarterly_financial_statements`→`unaudited_financial_statements`, bare `unaudited`→`unaudited_financial_statements`, `weekly_bulletin`→`bulletin`, `*_errata`→base type.
4b. **`is_financial` and `audited` are derived per the production prompt's explicit rule** (verbatim, not guessed): `is_financial = true` **only** for standalone financial statements — i.e. `document_type ∈ {audited_financial_statements, unaudited_financial_statements}`. `annual_report`, `prospectus`, and every news/other type are `is_financial = false` ("contain financials but are not financial statements"). `audited = true` for `audited_financial_statements`, `false` for unaudited/quarterly statements, `null` for non-FS docs (scored only where the golden value is non-null).
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
2. **Extract the first ~3 pages of text with `pypdf`**, matching the team's `DocumentHandler.extract_text_from_pdf` format (`--- Page {n} ---\n{page_text}`, blank line between pages, empty pages skipped), as the frozen `input_text`.
3. Emit a record: `{id, input_text, golden:{is_financial, document_type, company, symbol, year, audited}, source_filename, sensitivity:"public"}`.

Output: `dataset.jsonl` (text + labels — small, committed) and `MANIFEST.md` (counts, any excluded files, content hashes). The **PDFs are not committed** — they are fetched once locally for prep.

### Task + scorer

- `tasks/classification.py` — loads `dataset.jsonl` as Inspect `Sample`s (`input=input_text`, `metadata=golden`), solver applies the **harvested production prompt**: the Gemini `CLASSIFICATION_SYSTEM_PROMPT` (closed 29-value enum) as the system message + the production **text-path** user turn (`Please analyze and classify this document named "{filename}".\n\nDocument content:\n{text}`). The production system already has this text path, so we stay faithful rather than inventing. The system prompt interpolates the **official JSE symbol reference list** (`get_symbol_reference()`), harvested and included so symbol classification is fair. Single generation; parse the model's JSON.
- `scorers/classification.py` — pure per-field comparison, then a thin `@scorer` adapter (the slice-① template). Inspect dict-valued `Score` with per-field metrics + the headline.

## Scoring (mirrors `calculate_metrics.py`)

Per field, per document:

| Field | Rule |
|---|---|
| `is_financial` | boolean exact |
| `audited` | boolean exact |
| `document_type` | exact string equality, no normalization (golden mapped into the 29-value enum) |
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
- Already harvested (verbatim, 2026-06-21): the Gemini `CLASSIFICATION_SYSTEM_PROMPT` + text-path user turn, the 29-value `document_type` enum, the `is_financial`/`audited` rules, `normalize_company_name` and the per-field comparison code, and `DocumentHandler.extract_text_from_pdf`. Still to fetch once: `get_symbol_reference()` (the JSE symbol list) for the system prompt.

## Open items

_Resolved by the 2026-06-21 build-fact harvest:_ the `is_financial` rule (FS-only; `annual_report` & `prospectus` = false), the 29-value `document_type` enum + filename→enum map, the verbatim prompt, the scoring code, and the `pypdf` extraction format.

Remaining:
- Fetch `get_symbol_reference()` output (official JSE symbol list) for the system prompt — one-time build fetch.
- Number of pages to freeze (default 3; confirm signal coverage on a sample).
- Tier-2 fields await the S3 `golden_evaluation_dataset.json`.
