# Classification fixture manifest

- records: 70 / 99 PDFs
- dataset.jsonl sha256: aa130c78af38c01b
- source: Aeontsolutions/jse-doc-workflows golden_dataset_documents
- input: first 3 pages text (pypdf); labels derived from filenames
- symbols: derived from the 99 dataset filenames — the production JSE symbol source is a DynamoDB table needing AWS credentials, not reachable at build time. All symbols present in this dataset are captured; the official list may hold additional instruments. Known artifact: Kintyre Holdings appears as both KYNTR (used in the dataset) and KNTYR (an excluded file); both are in the prompt's symbol reference.

## Excluded (29)

_All 29 exclusions are scanned/image PDFs with no extractable text in the first 3 pages — classifiable only via OCR/multimodal input, which is out of scope for this text-input benchmark (v1)._

- amg_packaging_&_paper_company_limited-AMG-unaudited_financial_statements_31-may-2015.pdf (no extractable text in first 3 pages)
- amg_packaging_&_paper_company_limited-AMG-unaudited_financial_statements_31-may-2019.pdf (no extractable text in first 3 pages)
- atlantic_hardware_and_plumbing_company_limited-AHPC-audited_financial_statements_31-december-2024.pdf (no extractable text in first 3 pages)
- barita_investments_limited-BIL-audited_financial_statements_30-september-2016.pdf (no extractable text in first 3 pages)
- cable_&_wireless_jamaica_limited-CWJ-quarterly_financial_statements_10-april-2017.pdf (no extractable text in first 3 pages)
- cargo_handlers_limited-CHL-unaudited_financial_statements_31-march-2015.pdf (no extractable text in first 3 pages)
- cargo_handlers_limited-CHL-unaudited_financial_statements_31-march-2021.pdf (no extractable text in first 3 pages)
- caribbean_assurance_brokers_limited-cabrokers-unaudited_financial_statements-period_ended_march-31-2024.pdf (no extractable text in first 3 pages)
- caribbean_cream_limited-kremi-unaudited-period_ended_may-31-2023.pdf (no extractable text in first 3 pages)
- caribbean_producers_jamaica_limited-cpj-unaudited_financial_statements-period_ended_december-31-2021.pdf (no extractable text in first 3 pages)
- community_&_workers_of_jamaica_ccu_deffered_share-CWJDEFERREDA-audited_financial_statements_31-dec-20.pdf (no extractable text in first 3 pages)
- consolidated_bakeries_(jamaica)_limited-PURITY-unaudited_financial_statements_30-september-2022.pdf (no extractable text in first 3 pages)
- eppley_caribbean_property_fund_limited_scc_cpfv-_general_meetings_2020-12-30.pdf (no extractable text in first 3 pages)
- eppley_caribbean_property_fund_limited_scc_cpfv_nav_2021-07-30.pdf (no extractable text in first 3 pages)
- gracekennedy_limited_gk_dividend_declaration_2021-11-11.pdf (no extractable text in first 3 pages)
- indies_pharma_jamaica_limited-INDIES-audited_financial_statements_31-october-2020.pdf (no extractable text in first 3 pages)
- ironrock_insurance_company_limited-ROC-audited_financial_statements_31-december-2018.pdf (no extractable text in first 3 pages)
- jamaica_broilers_group_jbg_trading_in_shares_2021-07-16.pdf (no extractable text in first 3 pages)
- jetcon_corporation_limited_jetcon-_general_meetings_2020-06-15.pdf (no extractable text in first 3 pages)
- jmmb_group_limited_jmmbgl_other_company_news_2015-07-29.pdf (no extractable text in first 3 pages)
- key_insurance_company_limited-KEY-audited_financial_statements_31-december-2016.pdf (no extractable text in first 3 pages)
- kintyre_holdings_(ja)_limited_kntyr-_general_meetings_3_2021-07-05.pdf (no extractable text in first 3 pages)
- lasco_manufacturing_limited-lasm-unaudited_financial_statements-period_ended_september-30-2022.pdf (no extractable text in first 3 pages)
- ncb_financial_group_limited_ncbfg_acquisitions_mergers_and_disposals_2017-12-01.pdf (no extractable text in first 3 pages)
- qwi_investments_limited_qwi_nav_2022-12-09.pdf (no extractable text in first 3 pages)
- qwi_investments_limited_qwi_nav_2023-03-03.pdf (no extractable text in first 3 pages)
- qwi_investments_limited_qwi_trading_in_shares_2023-03-22.pdf (no extractable text in first 3 pages)
- sterling_investments_limited-SIL-unaudited_financial_statements_30-september-2015.pdf (no extractable text in first 3 pages)
- wigton_energy_limited-WIG-unaudited_financial_statements_30-june-2019.pdf (no extractable text in first 3 pages)
