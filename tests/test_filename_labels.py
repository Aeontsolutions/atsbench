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


def test_year_in_prefix_day_only_in_suffix():
    lab = parse_filename("acme_2019_holdings-ACME-audited_financial_statements_september-30.pdf", {"ACME"})
    assert lab.year == "2019"


def test_short_token_not_matched_inside_word():
    lab = parse_filename("navigator_holdings-NAVH-annual_report_2019.pdf", {"NAVH"})
    assert lab.document_type == "annual_report"


def test_nav_matches_when_delimiter_bounded():
    lab = parse_filename("qwi_investments_limited_qwi_nav_2022-12-09.pdf", {"QWI"})
    assert lab.document_type == "nav"


def test_company_starting_with_jse_is_not_jse_level():
    lab = parse_filename("jseg_holdings_limited-JSEG-annual_report_2022.pdf", {"JSEG"})
    assert lab.company is not None and lab.symbol == "JSEG"
