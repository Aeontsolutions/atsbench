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
