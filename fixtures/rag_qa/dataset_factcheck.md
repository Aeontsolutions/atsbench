# Fact-check: JSE companies dataset

**Source file:** `dataset.jsonl` (13 rows) · **Checked:** 21 Jun 2026 · All figures in Jamaican dollars (J$).

## Bottom line

Of the 10 rows containing checkable financial claims, **3 hold up, 7 are wrong or materially off.** The figures look synthetic — several match the *wrong* year or no reported number at all. If this is an eval set, the `expected_facts` encode incorrect "ground truth," so a model giving the *real* numbers would be graded wrong.

Most serious error: **row 2 says NCBFG revenue "grew ~9%" in FY2023 — it actually *fell* ~6%, and net profit collapsed 56%.** The direction is reversed.

## Row-by-row verdict

| Row | Claim in dataset | Reality (reported) | Verdict |
|---|---|---|---|
| 1 `ncbfg_revenue_2023` | NCBFG FY2023 total revenue **J$145.2bn** | FY2023 net operating income **J$137.26bn** (net banking & investment result J$113.03bn). J$145.2bn ≈ NCBFG's *FY2022* figure (J$145.31bn) | ✗ Wrong (looks like FY2022 number) |
| 2 `ncbfg_revenue_yoy` | FY2023 J$145.2bn vs FY2022 J$132.8bn → **grew ~9%** | Net operating income J$137.26bn (FY23) vs **J$145.31bn (FY22) → fell ~6%**. Neither dataset figure matches | ✗ Wrong — direction reversed |
| 3 `ncbfg_income_mix_2023` | NII **J$78bn** > non-interest **J$67.2bn** | NII **J$62.80bn**; non-interest income ≈ J$74.5bn (fees J$28.1bn + insurance J$24.2bn + gains). Non-interest was actually *larger* | ✗ Wrong figures; conclusion also questionable |
| 4 `gk_net_profit_2023` | GraceKennedy FY2023 net profit **~J$8.5bn** | Group profit after tax **J$8.4bn** (attributable to stockholders J$7.8bn) | ✓ Approximately correct (matches group PAT) |
| 5 `jbg_revenue_trend` | JBG revenue J$75bn → J$85bn → **J$96bn** (FY21–23), rising | Actual ~J$57bn → ~J$75.7bn → **J$91.4bn**. Rising trend right; every figure overstated | ◐ Trend correct, figures wrong |
| 6 `sgj_eps_2023` | Scotia Group FY2023 EPS **J$3.20** | FY2023 EPS **J$5.54** (FY2022 was J$3.75). J$3.20 matches no year | ✗ Wrong |
| 7 `car_net_profit_yoy` | Carreras FY2023 **J$3.1bn** vs FY2022 **J$2.9bn** → +~7% | FY ended Mar-2023 ≈ **J$4.7bn** (EPS ~J$0.97) vs ~J$3.8bn → ~+25%. Both figures too low | ◐ Growth direction right, figures wrong |
| 8 `ncbfg_vs_sgj_revenue` | NCBFG J$145.2bn > SGJ J$95bn | NCBFG (~J$137bn) **is** bigger than SGJ (~J$53bn operating income), but both dataset figures are wrong (SGJ badly overstated) | ◐ Conclusion right, figures wrong |
| 9 `wig_revenue_2023` | Wigton FY2023 total revenue **~J$2.4bn** | FY ended Mar-2023 ≈ **J$2.4bn** (implied from FY2024 J$2.22bn, −7.3%) | ✓ Approximately correct |
| 10 `jmmbgl_net_profit_2023` | JMMB Group FY2023 net profit **J$6.3bn** | Reported **J$6.3bn** for year ended 31 Mar 2023 | ✓ Correct |
| 11–13 (negative cases) | No financial claim to verify (behavioral tests) | — | n/a — but row 12's context reuses the wrong NCBFG J$145.2bn figure |

## Notes

- **Fiscal years differ** and the dataset doesn't specify period ends. NCBFG ends 30 Sep; GraceKennedy 31 Dec; Jamaica Broilers ~29 Apr; Scotia Group 31 Oct; JMMB 31 Mar; Wigton 31 Mar.
- **Carreras changed its year-end** from 31 March to 31 December. For the 12 months ended Dec-2023 net profit was J$3.61bn and Dec-2024 was J$6.23bn — still well above the dataset's J$3.1bn.
- The "J$'000" units in the context are interpreted correctly (e.g. 145,200,000 = J$145.2bn).

## Sources

- [NCBFG FY2023 results — Mayberry](https://www.mayberryinv.com/ncbfg-reports-68-decline-in-year-end-net-profit-attr-to-shareholders/) · [NCBFG Q4 2023 report (PDF)](https://www.myncb.com/NCBFinancialGroup/media/NCB-Financial-Group/Main-Librarie/NCB-Financial-Group-Limited-NCBFG-Financial-Results-Year-Ended-September-30-2023.pdf)
- [GraceKennedy 2023: revenue J$126.39bn, PBT J$9.67bn, PAT J$8.4bn](https://gracekennedy.com/media-center-press/gracekennedy-revenues-up-7-3-to-j126-39-billion-pre-tax-profits-up-10-3-to-j9-67-billion/)
- [Jamaica Broilers sales J$91.4bn, FY ending Apr 2023 — Gleaner](https://jamaica-gleaner.com/article/business/20230712/jamaica-broilers-sales-climb-new-record)
- [Scotia Group Jamaica FY2023: EPS J$5.54, net profit J$17.23bn — Gleaner](http://past.jamaica-gleaner.com/article/business/20231213/scotia-profit-beats-ncb-first-time-decade)
- [Carreras results (Dec-2024 audited; prior-year comparatives) — Mayberry](https://www.mayberryinv.com/car-report-year-end-net-profit-of-6-23-billion/)
- [JMMB Group J$6.3bn net profit, year ended 31 Mar 2023](https://jm.jmmb.com/jmmb-group-records-j63b-profit-challenging-market-conditions)
- [Wigton Windfarm Annual Report FY2023 — JSE](https://www.jamstockex.com/wigton-windfarm-limited-wig-annual-report-for-the-year-ended-march-31-2023/)
