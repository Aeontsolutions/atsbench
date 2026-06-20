# atsbench Slice ② — Document Classification Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a document-classification benchmark to atsbench that grades any model on classifying JSE regulatory filings (`is_financial`, `document_type`, `company`, `symbol`, `year`, `audited`) against ground truth derived from the team's filenames, scored the way their `calculate_metrics.py` scores it.

**Architecture:** Reuses the slice-① core unchanged except one small generalization to the report aggregator. New units: a heavily-tested **filename→labels parser**, a **first-pages PDF-text helper**, a **per-field classification scorer** (pure logic + thin `@scorer` adapter, the slice-① template), a **classification Inspect task**, and a one-time **fixture-build script** that produces a committed `dataset.jsonl`. Frozen input is the first ~3 pages of extracted text; every model sees identical text.

**Tech Stack:** Python 3.11+, Inspect AI, Pydantic, `pypdf` (new dep), pytest. Same uv environment as slice ①.

## Global Constraints

- Ground truth comes from the committed **filenames** in `jse-doc-workflows/golden_dataset_documents/`. The parser **flags-and-excludes** anything it cannot parse — it never silently mislabels.
- `document_type` golden = the production **29-value enum** (verbatim list in Task 1). Comparison is **exact string equality, no normalization**.
- `is_financial = true` **only** when `document_type ∈ {audited_financial_statements, unaudited_financial_statements}`; `annual_report`, `prospectus`, and all news/other types are `false`. `audited = true` for audited FS, `false` for unaudited/quarterly FS, `null` otherwise.
- `company` comparison uses the team's verbatim `normalize_company_name` (uppercase → `&`→`AND` → strip non-`[A-Z0-9\s]` → collapse spaces → trim). `symbol` is case-insensitive exact. `year` is string-exact.
- A field whose **golden value is `null`** (e.g. `audited` for non-FS, `company`/`symbol` for JSE-level docs) is **excluded** from that document's score.
- **Headline accuracy = macro per-field accuracy** = mean over documents of (correct fields / scored fields). It reaches the slice-① report via Inspect's `mean()` metric; the aggregator is generalized to read `accuracy`→`mean`→first metric.
- Frozen input text uses `pypdf` in the team's format: `--- Page {n} ---\n{page_text}`, blank line between pages, empty pages skipped; first 3 pages.
- Corpus is **published** JSE filings (sensitivity `public`); fixtures still carry the tag.
- Scorer = pure logic + thin `@scorer` adapter (the slice-① template). Bad model JSON → scored 0, never crashes.

---

### Task 1: Filename → labels parser

**Files:**
- Create: `src/atsbench/fixtures/__init__.py`
- Create: `src/atsbench/fixtures/filename_labels.py`
- Test: `tests/test_filename_labels.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `Labels` dataclass: `company: str | None`, `symbol: str | None`, `document_type: str`, `year: str`, `is_financial: bool`, `audited: bool | None`.
  - `parse_filename(filename: str, known_symbols: set[str]) -> Labels | None` — returns `None` when the type-token or year cannot be found (the "flag-and-exclude" signal). `known_symbols` is the set of official JSE symbol IDs (upper-cased) used to locate the symbol token.
  - `DOCUMENT_TYPES: set[str]` — the 29 canonical values.

- [ ] **Step 1: Write the failing test**

`tests/test_filename_labels.py`:
```python
from atsbench.fixtures.filename_labels import DOCUMENT_TYPES, parse_filename

# A representative known-symbol set (real build passes the full JSE list).
SYMS = {"138SL", "BIL", "DOLLA", "CAR", "DCOVE", "KREMI", "MGL", "AMG", "KYNTR", "CWJ"}


def test_dash_delimited_audited_fs():
    lab = parse_filename(
        "barita_investments_limited-BIL-audited_financial_statements-year_ended_september-30-2023.pdf",
        SYMS,
    )
    assert lab.document_type == "audited_financial_statements"
    assert lab.symbol == "BIL"
    assert lab.company == "barita investments limited"
    assert lab.year == "2023"
    assert lab.is_financial is True
    assert lab.audited is True


def test_underscore_delimited_annual_report_is_not_financial():
    lab = parse_filename("dolla_financial_services_limited_dolla_annual_report_2022.pdf", SYMS)
    assert lab.document_type == "annual_report"
    assert lab.symbol == "DOLLA"
    assert lab.year == "2022"
    assert lab.is_financial is False     # annual reports are NON-financial per the prompt rule
    assert lab.audited is None


def test_quarterly_maps_to_unaudited():
    lab = parse_filename(
        "1834_investments_limited-1834-quarterly_financial_statements_30-september-2018.pdf",
        {"1834"},
    )
    assert lab.document_type == "unaudited_financial_statements"
    assert lab.is_financial is True
    assert lab.audited is False
    assert lab.year == "2018"


def test_bare_unaudited_token():
    lab = parse_filename("caribbean_cream_limited-kremi-unaudited-period_ended_may-31-2023.pdf", SYMS)
    assert lab.document_type == "unaudited_financial_statements"
    assert lab.symbol == "KREMI"
    assert lab.year == "2023"


def test_news_type_and_two_digit_year():
    lab = parse_filename("carreras_limited_car_articles_2017-08-10.pdf", SYMS)
    assert lab.document_type == "articles"
    assert lab.is_financial is False
    assert lab.audited is None
    assert lab.year == "2017"


def test_leading_underscore_and_lowercase_symbol():
    lab = parse_filename("_mayberry_group_ltd.-MGL-unaudited_financial_statements_30-september-2019.pdf", SYMS)
    assert lab.symbol == "MGL"
    assert lab.document_type == "unaudited_financial_statements"
    assert lab.company == "mayberry group ltd"     # leading underscore + trailing dot stripped


def test_ampersand_company():
    lab = parse_filename("amg_packaging_&_paper_company_limited-AMG-unaudited_financial_statements_31-may-2015.pdf", SYMS)
    assert lab.symbol == "AMG"
    assert "&" in lab.company        # raw company keeps the &; normalization happens in the scorer
    assert lab.year == "2015"


def test_formerly_parenthetical():
    lab = parse_filename(
        "kintyre_holdings_(ja)_limited_(formerly_icreate_limited)-KYNTR-unaudited_financial_statements_30-september-2021.pdf",
        SYMS,
    )
    assert lab.symbol == "KYNTR"
    assert lab.document_type == "unaudited_financial_statements"
    assert lab.year == "2021"


def test_two_digit_trailing_year():
    lab = parse_filename(
        "community_&_workers_of_jamaica_ccu_deffered_share-CWJDEFERREDA-audited_financial_statements_31-dec-20.pdf",
        {"CWJDEFERREDA"},
    )
    assert lab.year == "2020"
    assert lab.document_type == "audited_financial_statements"


def test_jse_level_doc_has_no_company_or_symbol():
    lab = parse_filename("jse_weekly_bulletin_2017-05-26.pdf", SYMS)
    assert lab.document_type == "bulletin"
    assert lab.company is None
    assert lab.symbol is None
    assert lab.is_financial is False
    assert lab.year == "2017"


def test_unparseable_returns_none():
    assert parse_filename("totally_unstructured_document_name.pdf", SYMS) is None


def test_all_types_are_canonical():
    lab = parse_filename("eppley_limited_eply-_general_meetings_2018-05-04.pdf", {"EPLY"})
    assert lab.document_type in DOCUMENT_TYPES
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_filename_labels.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'atsbench.fixtures'`.

- [ ] **Step 3: Write `src/atsbench/fixtures/__init__.py` (empty) and `src/atsbench/fixtures/filename_labels.py`**

`src/atsbench/fixtures/__init__.py`: (empty file)

`src/atsbench/fixtures/filename_labels.py`:
```python
from __future__ import annotations

import re
from dataclasses import dataclass

DOCUMENT_TYPES: set[str] = {
    "audited_financial_statements", "unaudited_financial_statements", "annual_report",
    "general_meetings", "other_company_news", "acquisitions_mergers_and_disposals",
    "management_appointments_resignations_and_retirements", "jse_event_news",
    "director_appointments_resignations_and_retirements", "prospectus", "trading_in_shares",
    "dividend_declaration", "nav", "bulletin", "takeover_bids_and_scheme_of_arrangements",
    "dividend_consideration", "rights_issue", "jse_education_news", "jse_trading_news",
    "jse_monthly_regulatory_report", "basis_of_allotment", "disclosure_of_shareholders",
    "committee_news", "performance_report", "corporate_governance_policy_and_guidelines",
    "share_buy_back", "stock_split", "articles", "directors_circular", "delisting_notice",
}

# filename type-token -> canonical document_type. Order matters only via longest-match below.
_TYPE_MAP: dict[str, str] = {
    "audited_financial_statements": "audited_financial_statements",
    "unaudited_financial_statements": "unaudited_financial_statements",
    "quarterly_financial_statements": "unaudited_financial_statements",
    "annual_report_errata": "annual_report",
    "annual_report": "annual_report",
    "acquisitions_mergers_and_disposals": "acquisitions_mergers_and_disposals",
    "management_appointments_resignations_and_retirements": "management_appointments_resignations_and_retirements",
    "director_appointments_resignations_and_retirements": "director_appointments_resignations_and_retirements",
    "directors_circular": "directors_circular",
    "general_meetings": "general_meetings",
    "other_company_news": "other_company_news",
    "dividend_declaration": "dividend_declaration",
    "dividend_consideration": "dividend_consideration",
    "trading_in_shares": "trading_in_shares",
    "jse_event_news": "jse_event_news",
    "jse_trading_news": "jse_trading_news",
    "weekly_bulletin": "bulletin",
    "prospectus": "prospectus",
    "articles": "articles",
    "nav": "nav",
    "unaudited": "unaudited_financial_statements",  # bare token, matched only if nothing longer fits
}
# longest tokens first so "unaudited_financial_statements" beats "unaudited", etc.
_TYPE_TOKENS_BY_LEN = sorted(_TYPE_MAP, key=len, reverse=True)

_AUDITED_TYPE = "audited_financial_statements"
_UNAUDITED_TYPE = "unaudited_financial_statements"


@dataclass
class Labels:
    company: str | None
    symbol: str | None
    document_type: str
    year: str
    is_financial: bool
    audited: bool | None


def _find_year(suffix: str) -> str | None:
    four = re.findall(r"(?:19|20)\d{2}", suffix)
    if four:
        return four[-1]
    two = re.findall(r"(?<!\d)(\d{2})(?!\d)", suffix)
    if two:
        return "20" + two[-1]
    return None


def parse_filename(filename: str, known_symbols: set[str]) -> Labels | None:
    stem = filename[:-4] if filename.lower().endswith(".pdf") else filename
    lower = stem.lower()

    token = next((t for t in _TYPE_TOKENS_BY_LEN if t in lower), None)
    if token is None:
        return None
    doc_type = _TYPE_MAP[token]

    start = lower.index(token)
    prefix = stem[:start].strip(" -_")
    suffix = stem[start + len(token):]

    year = _find_year(suffix) or _find_year(prefix)
    if year is None:
        return None

    is_financial = doc_type in (_AUDITED_TYPE, _UNAUDITED_TYPE)
    audited = True if doc_type == _AUDITED_TYPE else (False if doc_type == _UNAUDITED_TYPE else None)

    # JSE-level documents have no company/symbol.
    if prefix.lower().startswith("jse"):
        return Labels(None, None, doc_type, year, is_financial, audited)

    tokens = [t for t in re.split(r"[-_]", prefix) if t]
    symbol = None
    sym_idx = None
    for i in range(len(tokens) - 1, -1, -1):
        if tokens[i].upper() in known_symbols:
            symbol = tokens[i].upper()
            sym_idx = i
            break

    company_tokens = tokens[:sym_idx] if sym_idx is not None else tokens
    # drop a trailing "(formerly ...)" parenthetical group from the company name
    company = " ".join(company_tokens).strip()
    company = re.sub(r"\(formerly[^)]*\)?", "", company).strip()
    company = company.replace(".", "").strip()
    company = re.sub(r"\s+", " ", company) or None

    return Labels(company, symbol, doc_type, year, is_financial, audited)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_filename_labels.py -v`
Expected: PASS (12 passed). If a real-filename edge case fails, fix the parser — the 99 filenames are the source of truth; do not weaken an assertion to pass.

- [ ] **Step 5: Commit**

```bash
git add src/atsbench/fixtures/__init__.py src/atsbench/fixtures/filename_labels.py tests/test_filename_labels.py
git commit -m "feat: filename->labels parser for classification ground truth"
```

---

### Task 2: First-pages PDF text helper

**Files:**
- Modify: `pyproject.toml` (add `pypdf>=4.0` to `dependencies`)
- Create: `src/atsbench/fixtures/pdf_text.py`
- Test: `tests/test_pdf_text.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `format_pages(pages: list[str | None]) -> str` — pure: joins pages as `--- Page {n} ---\n{text}` (1-based n), blank line between, skipping `None`/empty.
  - `first_pages_text(pdf_bytes: bytes, n: int = 3) -> str` — reads the first `n` pages with `pypdf` and returns `format_pages(...)`.

- [ ] **Step 1: Add the dependency**

In `pyproject.toml`, add `"pypdf>=4.0",` to the `dependencies` list, then:
```bash
uv pip install -e ".[dev]"
```

- [ ] **Step 2: Write the failing test (pure formatter + a tiny real PDF)**

`tests/test_pdf_text.py`:
```python
import base64

from atsbench.fixtures.pdf_text import first_pages_text, format_pages

# Minimal one-page PDF containing the text "Hello" (generated once, embedded here).
_ONE_PAGE_PDF = base64.b64decode(
    "JVBERi0xLjQKMSAwIG9iago8PC9UeXBlL0NhdGFsb2cvUGFnZXMgMiAwIFI+PgplbmRvYmoKMiAw"
    "IG9iago8PC9UeXBlL1BhZ2VzL0tpZHNbMyAwIFJdL0NvdW50IDE+PgplbmRvYmoKMyAwIG9iago8"
    "PC9UeXBlL1BhZ2UvUGFyZW50IDIgMCBSL01lZGlhQm94WzAgMCAyMDAgMjAwXS9SZXNvdXJjZXM8"
    "PC9Gb250PDwvRjEgNCAwIFI+Pj4+L0NvbnRlbnRzIDUgMCBSPj4KZW5kb2JqCjQgMCBvYmoKPDwv"
    "VHlwZS9Gb250L1N1YnR5cGUvVHlwZTEvQmFzZUZvbnQvSGVsdmV0aWNhPj4KZW5kb2JqCjUgMCBv"
    "YmoKPDwvTGVuZ3RoIDQ0Pj4Kc3RyZWFtCkJUIC9GMSAyNCBUZiAyMCAxMDAgVGQgKEhlbGxvKSBU"
    "agpFVAplbmRzdHJlYW0KZW5kb2JqCnhyZWYKMCA2CjAwMDAwMDAwMDAgNjU1MzUgZiAKMDAwMDAw"
    "MDAwOSAwMDAwMCBuIAowMDAwMDAwMDU4IDAwMDAwIG4gCjAwMDAwMDAxMTUgMDAwMDAgbiAKMDAw"
    "MDAwMDI0MSAwMDAwMCBuIAowMDAwMDAwMzEwIDAwMDAwIG4gCnRyYWlsZXIKPDwvU2l6ZSA2L1Jv"
    "b3QgMSAwIFI+PgpzdGFydHhyZWYKNDA0CiUlRU9GCg=="
)


def test_format_pages_skips_empty_and_numbers_from_one():
    out = format_pages(["alpha", None, "gamma"])
    assert out == "--- Page 1 ---\nalpha\n\n--- Page 3 ---\ngamma"


def test_first_pages_text_reads_pdf():
    out = first_pages_text(_ONE_PAGE_PDF, n=3)
    assert "--- Page 1 ---" in out
    assert "Hello" in out
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_pdf_text.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'atsbench.fixtures.pdf_text'`.

- [ ] **Step 4: Write `src/atsbench/fixtures/pdf_text.py`**

```python
from __future__ import annotations

import io

import pypdf


def format_pages(pages: list[str | None]) -> str:
    blocks = []
    for i, text in enumerate(pages, start=1):
        if text and text.strip():
            blocks.append(f"--- Page {i} ---\n{text}")
    return "\n\n".join(blocks)


def first_pages_text(pdf_bytes: bytes, n: int = 3) -> str:
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    pages: list[str | None] = []
    for page in reader.pages[:n]:
        pages.append(page.extract_text())
    return format_pages(pages)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_pdf_text.py -v`
Expected: PASS (2 passed). If `pypdf` extracts `Hello` with different spacing, relax the second assertion to `assert "Hello" in out.replace(" ", "")` — do not change the formatter.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/atsbench/fixtures/pdf_text.py tests/test_pdf_text.py
git commit -m "feat: first-pages pdf text extraction (pypdf, team format)"
```

---

### Task 3: Classification scorer

**Files:**
- Create: `src/atsbench/scorers/classification.py`
- Test: `tests/test_classification_scorer.py`

**Interfaces:**
- Consumes: nothing (pure logic); the `@scorer` adapter uses Inspect `Score`/`Target`/`TaskState`/`mean`/`stderr`.
- Produces:
  - `normalize_company_name(name: str | None) -> str` — verbatim from the team.
  - `score_fields(pred: dict, gold: dict) -> dict` — returns `{"per_field": {field: bool}, "scored": int, "correct": int, "fraction": float, "exact_record": bool}`; fields whose gold value is `None` are skipped.
  - `classification()` — Inspect `@scorer(metrics=[mean(), stderr()])`; `Score.value` = `fraction`; metadata carries `per_field` + `exact_record` + `format_ok`. Unparseable model JSON → `fraction = 0.0`, `format_ok = False`.

- [ ] **Step 1: Write the failing test**

`tests/test_classification_scorer.py`:
```python
from atsbench.scorers.classification import normalize_company_name, score_fields

GOLD = {
    "is_financial": True, "document_type": "audited_financial_statements",
    "company": "barita investments limited", "symbol": "BIL",
    "year": "2023", "audited": True,
}


def test_normalize_company_name():
    assert normalize_company_name("AMG Packaging & Paper Co., Ltd.") == "AMG PACKAGING AND PAPER CO LTD"
    assert normalize_company_name(None) == ""


def test_all_correct():
    pred = dict(GOLD, company="Barita Investments Limited", symbol="bil")  # casing/format differences
    r = score_fields(pred, GOLD)
    assert r["scored"] == 6 and r["correct"] == 6
    assert r["fraction"] == 1.0 and r["exact_record"] is True


def test_one_wrong_field():
    pred = dict(GOLD, document_type="unaudited_financial_statements")
    r = score_fields(pred, GOLD)
    assert r["correct"] == 5 and r["scored"] == 6
    assert r["fraction"] == 5 / 6 and r["exact_record"] is False
    assert r["per_field"]["document_type"] is False


def test_null_gold_field_is_skipped():
    gold = dict(GOLD, document_type="annual_report", is_financial=False, audited=None)
    pred = dict(gold, audited=False)  # model guessed audited but gold is null -> not scored
    r = score_fields(pred, gold)
    assert r["scored"] == 5            # audited excluded
    assert "audited" not in r["per_field"]


def test_year_is_string_exact():
    assert score_fields(dict(GOLD, year=2023), GOLD)["per_field"]["year"] is True   # 2023 -> "2023"
    assert score_fields(dict(GOLD, year="2022"), GOLD)["per_field"]["year"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_classification_scorer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'atsbench.scorers.classification'`.

- [ ] **Step 3: Write `src/atsbench/scorers/classification.py`**

```python
from __future__ import annotations

import json
import re

from inspect_ai.scorer import Score, Target, mean, scorer, stderr
from inspect_ai.solver import TaskState

_FIELDS = ("is_financial", "document_type", "company", "symbol", "year", "audited")


def normalize_company_name(name: str | None) -> str:
    if not name:
        return ""
    n = str(name).upper().replace("&", "AND")
    n = re.sub(r"[^A-Z0-9\s]", "", n)
    n = re.sub(r"\s+", " ", n)
    return n.strip()


def _field_correct(field: str, gold, pred) -> bool:
    if field == "company":
        return normalize_company_name(gold) == normalize_company_name(pred)
    if field == "symbol":
        return pred is not None and str(gold).upper() == str(pred).upper()
    if field in ("year",):
        return str(gold) == str(pred)
    if field in ("is_financial", "audited", "document_type"):
        return gold == pred
    return gold == pred


def score_fields(pred: dict, gold: dict) -> dict:
    per_field: dict[str, bool] = {}
    for field in _FIELDS:
        if gold.get(field) is None:
            continue
        per_field[field] = _field_correct(field, gold.get(field), pred.get(field))
    scored = len(per_field)
    correct = sum(1 for v in per_field.values() if v)
    return {
        "per_field": per_field,
        "scored": scored,
        "correct": correct,
        "fraction": correct / scored if scored else 0.0,
        "exact_record": scored > 0 and correct == scored,
    }


@scorer(metrics=[mean(), stderr()])
def classification():
    async def score(state: TaskState, target: Target) -> Score:
        gold = state.metadata["golden"]
        raw = state.output.completion
        try:
            start, end = raw.index("{"), raw.rindex("}") + 1
            pred = json.loads(raw[start:end])
            format_ok = isinstance(pred, dict)
        except (ValueError, json.JSONDecodeError):
            pred, format_ok = {}, False

        if not format_ok:
            return Score(value=0.0, answer=raw[:200],
                         metadata={"format_ok": False, "per_field": {}, "exact_record": False})

        r = score_fields(pred, gold)
        return Score(value=r["fraction"], answer=raw[:200],
                     metadata={"format_ok": True, "per_field": r["per_field"],
                               "exact_record": r["exact_record"], "scored": r["scored"]})

    return score
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_classification_scorer.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add src/atsbench/scorers/classification.py tests/test_classification_scorer.py
git commit -m "feat: per-field classification scorer (mirrors calculate_metrics.py)"
```

---

### Task 4: Generalize the report aggregator's headline metric

**Files:**
- Modify: `src/atsbench/report/aggregate.py` (the `accuracy_from_log` function)
- Test: `tests/test_aggregate_headline.py`

**Interfaces:**
- Consumes: an Inspect-style results object.
- Produces: `accuracy_from_log(log) -> float` now reads the metric named `accuracy`, else `mean`, else the first metric on the first scorer (so float-valued scorers using `mean()` — like classification — surface their headline). Behaviour for existing `accuracy`-named scorers is unchanged.

- [ ] **Step 1: Write the failing test**

`tests/test_aggregate_headline.py`:
```python
from dataclasses import dataclass

from atsbench.report.aggregate import accuracy_from_log


@dataclass
class _M:
    value: float


@dataclass
class _S:
    metrics: dict


@dataclass
class _R:
    scores: list


@dataclass
class _Log:
    results: object


def test_prefers_accuracy_then_mean():
    log_acc = _Log(_R([_S({"accuracy": _M(0.9), "mean": _M(0.5)})]))
    assert accuracy_from_log(log_acc) == 0.9

    log_mean = _Log(_R([_S({"mean": _M(0.77), "stderr": _M(0.1)})]))
    assert accuracy_from_log(log_mean) == 0.77


def test_falls_back_to_first_metric():
    log_other = _Log(_R([_S({"f1": _M(0.42)})]))
    assert accuracy_from_log(log_other) == 0.42


def test_no_results_is_zero():
    assert accuracy_from_log(_Log(None)) == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_aggregate_headline.py -v`
Expected: FAIL — the current `accuracy_from_log` returns 0.0 for the `mean`/`f1` cases.

- [ ] **Step 3: Update `accuracy_from_log` in `src/atsbench/report/aggregate.py`**

Replace the existing `accuracy_from_log` function body with:
```python
def accuracy_from_log(log) -> float:
    """Headline accuracy: prefer an 'accuracy' metric, then 'mean', then the
    first metric on the first scorer. Float-valued scorers (e.g. classification's
    macro per-field accuracy via mean()) surface their headline this way."""
    if log.results is None or not log.results.scores:
        return 0.0
    for score in log.results.scores:
        for key in ("accuracy", "mean"):
            metric = score.metrics.get(key)
            if metric is not None:
                return float(metric.value)
    first = log.results.scores[0].metrics
    if first:
        return float(next(iter(first.values())).value)
    return 0.0
```

- [ ] **Step 4: Run the new test and the existing aggregate tests**

Run: `uv run pytest tests/test_aggregate_headline.py tests/test_aggregate.py -v`
Expected: PASS (all). The slice-① `test_aggregate.py` still passes because the `accuracy` branch is unchanged.

- [ ] **Step 5: Commit**

```bash
git add src/atsbench/report/aggregate.py tests/test_aggregate_headline.py
git commit -m "feat: aggregator reads accuracy->mean->first headline metric"
```

---

### Task 5: Classification task, workflow gate, and end-to-end smoke

**Files:**
- Create: `src/atsbench/tasks/classification.py`
- Create: `fixtures/classification/system_prompt.txt` (the harvested system prompt; symbol reference appended in Task 6)
- Create: `tests/fixtures/classification_smoke.jsonl` (3 hand-written records)
- Modify: `workflows.yaml` (add `classification`)
- Test: `tests/test_classification_task.py`

**Interfaces:**
- Consumes: `classification` scorer (Task 3); `load_workflows` (slice ①); the dataset JSONL format `{id, input_text, golden{...}, source_filename, sensitivity}`.
- Produces: `load_dataset(path) -> list[Sample]`; `classification_task(dataset_path=...) -> Task`; `USER_TEMPLATE` (the text-path user turn).

- [ ] **Step 1: Create the smoke dataset and system prompt stub**

`tests/fixtures/classification_smoke.jsonl` (one JSON object per line):
```json
{"id": "doc1", "input_text": "--- Page 1 ---\nBARITA INVESTMENTS LIMITED\nAudited Financial Statements\nYear ended September 30, 2023", "golden": {"is_financial": true, "document_type": "audited_financial_statements", "company": "barita investments limited", "symbol": "BIL", "year": "2023", "audited": true}, "source_filename": "barita-BIL-audited_financial_statements-2023.pdf", "sensitivity": "public"}
{"id": "doc2", "input_text": "--- Page 1 ---\nDOLLA FINANCIAL SERVICES LIMITED\nAnnual Report 2022", "golden": {"is_financial": false, "document_type": "annual_report", "company": "dolla financial services limited", "symbol": "DOLLA", "year": "2022", "audited": null}, "source_filename": "dolla_annual_report_2022.pdf", "sensitivity": "public"}
{"id": "doc3", "input_text": "--- Page 1 ---\nJSE WEEKLY BULLETIN", "golden": {"is_financial": false, "document_type": "bulletin", "company": null, "symbol": null, "year": "2017", "audited": null}, "source_filename": "jse_weekly_bulletin_2017.pdf", "sensitivity": "public"}
```

`fixtures/classification/system_prompt.txt` — fetch the verbatim production prompt from the repo (do not paraphrase):
```bash
gh api repos/Aeontsolutions/jse-doc-workflows/contents/src/gemini3/client.py --jq .content | base64 -d > /tmp/client.py
```
Open `/tmp/client.py`, find the `CLASSIFICATION_SYSTEM_PROMPT` string constant (around lines 104–148), and write its exact string value to `fixtures/classification/system_prompt.txt` — copy the content verbatim, leaving the literal token `{_INSTRUMENT_SYMBOL_REFERENCE}` in place (Task 6 replaces it with the real symbol list). The constant's value begins `You are a helpful assistant tasked with analyzing and classifying PDFs supplied to you.` and ends `...outside the JSON structure.` — include everything in between, including the full 29-value `document_type` enum and the page-localization fields, so models perform the exact production task.

- [ ] **Step 2: Write the failing test**

`tests/test_classification_task.py`:
```python
import json
from pathlib import Path

from inspect_ai import eval as inspect_eval
from inspect_ai.model import ModelOutput, get_model

from atsbench.cli import main
from atsbench.tasks.classification import classification_task, load_dataset

ROOT = Path(__file__).resolve().parent.parent
SMOKE = Path(__file__).resolve().parent / "fixtures" / "classification_smoke.jsonl"


def test_load_dataset_reads_records():
    samples = load_dataset(SMOKE)
    assert len(samples) == 3
    assert samples[0].metadata["golden"]["symbol"] == "BIL"


def test_full_loop_with_mock_model(tmp_path, capsys):
    # Mock returns the exactly-correct classification JSON for each of the 3 docs,
    # so the model scores 1.0 and passes the gate — exercises the success path.
    golden = [json.loads(line)["golden"] for line in SMOKE.read_text().splitlines()]
    outputs = [ModelOutput.from_content("mockllm/model", json.dumps(g)) for g in golden]
    model = get_model("mockllm/model", custom_outputs=outputs, memoize=False)

    log_dir = tmp_path / "logs"
    inspect_eval(classification_task(dataset_path=str(SMOKE)), model=model, log_dir=str(log_dir))

    json_out = tmp_path / "report.json"
    rc = main(["report", "--logs", str(log_dir), "--workflow", "classification",
               "--models", str(ROOT / "models.yaml"), "--workflows", str(ROOT / "workflows.yaml"),
               "--json", str(json_out)])
    assert rc == 0
    row = json.loads(json_out.read_text())["rows"][0]
    assert row["accuracy"] == 1.0
    assert row["passed_gate"] is True
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_classification_task.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'atsbench.tasks.classification'`.

- [ ] **Step 4: Write `src/atsbench/tasks/classification.py`**

```python
from __future__ import annotations

import json
from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.solver import generate, system_message

from atsbench.scorers.classification import classification

_PROMPT_PATH = Path(__file__).resolve().parent.parent.parent.parent / "fixtures" / "classification" / "system_prompt.txt"

USER_TEMPLATE = (
    'Please analyze and classify this document named "{filename}".\n\n'
    "Document content:\n{text}"
)


def _system_prompt() -> str:
    return _PROMPT_PATH.read_text()


def load_dataset(path: str | Path) -> list[Sample]:
    samples = []
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        user = USER_TEMPLATE.format(filename=rec["source_filename"], text=rec["input_text"])
        samples.append(Sample(id=rec["id"], input=user, metadata={"golden": rec["golden"]}))
    return samples


@task
def classification_task(dataset_path: str = "fixtures/classification/dataset.jsonl") -> Task:
    return Task(
        dataset=load_dataset(dataset_path),
        solver=[system_message(_system_prompt()), generate()],
        scorer=classification(),
    )
```

- [ ] **Step 5: Add the `classification` workflow to `workflows.yaml`**

Append under `workflows:`:
```yaml
  - name: classification
    gate:
      min_accuracy: 0.7
      primary_axis: cost
```

- [ ] **Step 6: Run the test**

Run: `uv run pytest tests/test_classification_task.py -v`
Expected: PASS (2 passed), no network. If `system_message`/`generate` import paths differ in the installed Inspect, run `uv run python -c "import inspect_ai.solver as s; print([x for x in dir(s) if 'message' in x or x=='generate'])"` and adjust the imports, then re-run.

- [ ] **Step 7: Commit**

```bash
git add src/atsbench/tasks/classification.py fixtures/classification/system_prompt.txt tests/fixtures/classification_smoke.jsonl tests/test_classification_task.py workflows.yaml
git commit -m "feat: classification Inspect task, gate, and zero-cost e2e smoke"
```

---

### Task 6: Build the real fixture dataset (99 docs)

**Files:**
- Create: `fixtures/classification/build.py`
- Create (generated, committed): `fixtures/classification/dataset.jsonl`, `fixtures/classification/MANIFEST.md`
- Modify (generated): `fixtures/classification/system_prompt.txt` (interpolate the real symbol list)

**Interfaces:**
- Consumes: `parse_filename`/`Labels` (Task 1), `first_pages_text` (Task 2).
- Produces: the committed benchmark dataset. This task runs the build and commits its output; there is no unit test — the deliverable is verified by the assertions in Step 4.

- [ ] **Step 1: Fetch the PDFs and the symbol reference once (local, not committed)**

```bash
# Partial clone — only the golden_dataset_documents blobs (a few hundred MB).
git clone --filter=blob:none --sparse https://github.com/Aeontsolutions/jse-doc-workflows.git /tmp/jse
git -C /tmp/jse sparse-checkout set golden_dataset_documents
ls /tmp/jse/golden_dataset_documents | wc -l    # expect 99

# Harvest the official JSE symbol reference the production prompt interpolates.
gh api repos/Aeontsolutions/jse-doc-workflows/contents/src/utils/instrument_lookup.py --jq .content | base64 -d > /tmp/instrument_lookup.py
```
Inspect `/tmp/instrument_lookup.py` to obtain the symbol list. Build a `symbols.json` of `{"SYMBOL": "Company Name", ...}` (the known-symbol set is `set(symbols.keys())`). If the symbols come from a static structure in that file, extract them directly; if they require a runtime data source you cannot reach, write `symbols.json` from the distinct symbols you can recover and **log the limitation in MANIFEST** (symbol scores will be depressed-but-comparable). Also render the human-readable reference block (`SYMBOL — Company Name` per line) for the prompt.

- [ ] **Step 2: Write `fixtures/classification/build.py`**

```python
"""One-time prep: build the committed classification dataset from local PDFs.

Usage: uv run python fixtures/classification/build.py /tmp/jse/golden_dataset_documents /tmp/symbols.json
Outputs fixtures/classification/dataset.jsonl and MANIFEST.md, and interpolates
the symbol reference into system_prompt.txt. PDFs are NOT committed.
"""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path

from atsbench.fixtures.filename_labels import parse_filename
from atsbench.fixtures.pdf_text import first_pages_text

HERE = Path(__file__).resolve().parent


def main(pdf_dir: str, symbols_json: str) -> None:
    symbols = json.loads(Path(symbols_json).read_text())
    known = {s.upper() for s in symbols}
    records, excluded = [], []

    for pdf in sorted(Path(pdf_dir).glob("*.pdf")):
        labels = parse_filename(pdf.name, known)
        if labels is None:
            excluded.append(pdf.name)
            continue
        try:
            text = first_pages_text(pdf.read_bytes(), n=3)
        except Exception as e:  # corrupt/encrypted PDF -> exclude, don't crash
            excluded.append(f"{pdf.name} (text extraction failed: {e})")
            continue
        if not text.strip():
            excluded.append(f"{pdf.name} (no extractable text in first 3 pages)")
            continue
        records.append({
            "id": pdf.stem,
            "input_text": text,
            "golden": asdict(labels),
            "source_filename": pdf.name,
            "sensitivity": "public",
        })

    out = HERE / "dataset.jsonl"
    out.write_text("\n".join(json.dumps(r) for r in records) + "\n")

    digest = hashlib.sha256(out.read_bytes()).hexdigest()[:16]
    (HERE / "MANIFEST.md").write_text(
        f"# Classification fixture manifest\n\n"
        f"- records: {len(records)} / {len(records) + len(excluded)} PDFs\n"
        f"- dataset.jsonl sha256: {digest}\n"
        f"- source: Aeontsolutions/jse-doc-workflows golden_dataset_documents\n"
        f"- input: first 3 pages text (pypdf); labels derived from filenames\n\n"
        f"## Excluded ({len(excluded)})\n" + "\n".join(f"- {e}" for e in excluded) + "\n"
    )

    # interpolate the symbol reference into the system prompt
    ref = "\n".join(f"{s} — {name}" for s, name in sorted(symbols.items()))
    sp = HERE / "system_prompt.txt"
    sp.write_text(sp.read_text().replace("{_INSTRUMENT_SYMBOL_REFERENCE}", ref))

    print(f"wrote {len(records)} records, excluded {len(excluded)}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
```

- [ ] **Step 3: Run the build**

```bash
uv run python fixtures/classification/build.py /tmp/jse/golden_dataset_documents /tmp/symbols.json
```
Expected: `wrote N records, excluded M` with `N + M == 99` and `N` ≥ ~85 (most should parse). Read `fixtures/classification/MANIFEST.md` and confirm the excluded list is small and each exclusion has a reason. If many docs are excluded for parsing, fix `parse_filename` (Task 1) against the offending names and re-run — do not lower the bar by mislabeling.

- [ ] **Step 4: Verify the dataset and run the real benchmark plumbing on the mock**

```bash
uv run python -c "
import json
recs=[json.loads(l) for l in open('fixtures/classification/dataset.jsonl')]
print('records', len(recs))
assert all(r['golden']['document_type'] for r in recs)
fin=[r for r in recs if r['golden']['is_financial']]
print('financial docs', len(fin))
assert len(fin) >= 30
"
```
Expected: prints counts; no assertion error.

- [ ] **Step 5: Commit the generated dataset**

```bash
git add fixtures/classification/build.py fixtures/classification/dataset.jsonl fixtures/classification/MANIFEST.md fixtures/classification/system_prompt.txt
git commit -m "feat: build committed classification dataset (99 JSE filings)"
```

---

## Self-Review

**Spec coverage:**
- Filenames → golden labels (6 fields) → Task 1. ✓
- 29-value enum + filename→enum map (quarterly→unaudited, weekly_bulletin→bulletin, bare unaudited, *_errata) → Task 1 `_TYPE_MAP`. ✓
- `is_financial` FS-only; `audited` true/false/null → Task 1 derivation. ✓
- First ~3 pages text in the team's `--- Page n ---` format via pypdf → Task 2. ✓
- Scorer mirrors `calculate_metrics.py` (normalize_company_name verbatim, document_type exact, symbol case-insensitive, year string, null-skip) → Task 3. ✓
- Headline = macro per-field accuracy reaching the report → Task 3 (`mean()`) + Task 4 (aggregator generalization). ✓
- Harvested production prompt (system + text user turn) + symbol reference → Task 5 + Task 6 Step 1. ✓
- Classification task + `classification` workflow gate → Task 5. ✓
- Zero-cost mock end-to-end exercising the success path → Task 5. ✓
- Committed dataset from the 99 PDFs, flag-and-exclude unparseable, MANIFEST provenance/hashes, public sensitivity → Task 6. ✓
- Plugs into slice-① providers/report/CLI unchanged (except Task 4) → Tasks 4/5. ✓

**Deferred (own later work):** Tier-2 fields (`period_end` exact, statement-presence F1, page-localization IoU) need the S3 `golden_evaluation_dataset.json`; the scorer's null-skip + `_FIELDS` list extend into them without rework. Per-field breakdown + format-failure rate as scorecard columns (currently in Score metadata / Inspect View).

**Placeholder scan:** none. The system prompt text and symbol list are data assets fetched/pasted at build time (Tasks 5/6), not vague code placeholders.

**Type consistency:** `Labels` fields = `score_fields`/golden keys = smoke-fixture `golden` keys (`is_financial, document_type, company, symbol, year, audited`). `parse_filename(name, known_symbols)` signature consistent across Tasks 1/6. Dataset record shape `{id, input_text, golden, source_filename, sensitivity}` consistent across Tasks 5/6. `classification()` scorer returns float `Score.value` consumed by Task 4's `mean`-aware aggregator. ✓
