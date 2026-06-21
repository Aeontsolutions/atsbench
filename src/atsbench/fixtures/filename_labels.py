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


def _match_token(lower: str) -> tuple[str, int] | None:
    """Longest type-token that appears delimiter-bounded; returns (token, start_index)."""
    for tok in _TYPE_TOKENS_BY_LEN:
        m = re.search(r"(?:^|[-_])(" + re.escape(tok) + r")(?:$|[-_])", lower)
        if m:
            return tok, m.start(1)
    return None


def parse_filename(filename: str, known_symbols: set[str]) -> Labels | None:
    stem = filename[:-4] if filename.lower().endswith(".pdf") else filename
    lower = stem.lower()

    matched = _match_token(lower)
    if matched is None:
        return None
    token, start = matched
    doc_type = _TYPE_MAP[token]

    prefix = stem[:start].strip(" -_")
    suffix = stem[start + len(token):]

    if re.search(r"(?:19|20)\d{2}", suffix):
        year = _find_year(suffix)
    elif re.search(r"(?:19|20)\d{2}", prefix):
        year = _find_year(prefix)
    else:
        year = _find_year(suffix) or _find_year(prefix)
    if year is None:
        return None

    is_financial = doc_type in (_AUDITED_TYPE, _UNAUDITED_TYPE)
    audited = True if doc_type == _AUDITED_TYPE else (False if doc_type == _UNAUDITED_TYPE else None)

    # JSE-level documents have no company/symbol.
    if re.match(r"jse(?:[-_ ]|$)", prefix.lower()):
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
