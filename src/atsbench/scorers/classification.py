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


_LEGAL_SUFFIXES = {
    "ltd", "limited", "plc", "inc", "incorporated", "corp", "corporation",
    "co", "company", "llc", "lp",
}


def _company_tokens(name: str | None) -> set[str]:
    """Distinctive company tokens: lowercase, &->and, strip parentheticals,
    legal-form suffixes (ltd/limited/company/...), and a leading 'the'."""
    if not name:
        return set()
    n = str(name).lower().replace("&", "and")
    n = re.sub(r"\([^)]*\)", " ", n)
    n = re.sub(r"[^a-z0-9\s]", " ", n)
    return {t for t in n.split() if t and t != "the" and t not in _LEGAL_SUFFIXES}


def company_match(gold: str | None, pred: str | None) -> bool:
    """Lenient match for filename-derived company labels: ignores Ltd/Limited and
    parenthetical/cruft differences. The filename golden often abbreviates or carries
    extra tokens, so a >=2-token subset on either side counts as a match."""
    g, p = _company_tokens(gold), _company_tokens(pred)
    if not g or not p:
        return g == p
    if g == p:
        return True
    return (g <= p or p <= g) and min(len(g), len(p)) >= 2


def _field_correct(field: str, gold, pred) -> bool:
    if field == "company":
        return company_match(gold, pred)
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
        # year is only well-defined for financial statements; the production
        # prompt forbids using the filing/publication date, so we do not score
        # year on non-financial docs (whose filename-derived year IS the filing date).
        if field == "year" and gold.get("is_financial") is False:
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
