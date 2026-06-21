# RAG Q&A fixture manifest

- records: 13 (10 positive, 3 negative)
- workflow: rag_qa (financial path, frozen single-turn isolated generation)
- input per record: `{question, context, expected_facts[], category}`

## ✓ Verified (2026-06-21)

Figures were **fact-checked against public sources** (company results releases, Mayberry,
the Gleaner, JSE filings) — see [`dataset_factcheck.md`](dataset_factcheck.md) for the
row-by-row sources. The original draft figures were synthetic and mostly wrong; corrections:

- **NCBFG** revenue rows reframed to **net operating income** — J$137.26bn FY2023 vs
  J$145.31bn FY2022, so it **fell ~6%** (the draft had the direction reversed).
- **NCBFG income mix:** NII ~J$62.8bn < non-interest ~J$74.5bn — non-interest is the larger
  contributor (the draft conclusion was flipped).
- Corrected to reported figures: **JBG** (~57 / 75.7 / 91.4bn), **SGJ EPS** (J$5.54),
  **Carreras** (~J$4.7bn vs ~J$3.8bn), **SGJ NOI** (~J$53bn), **GK group PAT** (J$8.4bn).
- **Fiscal period-ends added** to each context (NCBFG 30-Sep, GK 31-Dec, JBG ~Apr, SGJ
  31-Oct, JMMB 31-Mar, WIG 31-Mar, CAR 31-Mar) since fiscal years differ.

Some figures are approximate (`~`); the `expected_facts` are phrased with tolerance so the
judge accepts close answers. Companies (real JSE symbols): NCBFG, GK, JBG, SGJ, CAR, WIG, JMMBGL.

## Validity rule

Every `expected_fact` must be answerable from that record's `context`. Holds by construction
for all 13 records; re-check after any figure edit.

## Negative cases

3 records test the production safety/scope rules: off-topic request (decline + redirect),
personalized buy/sell advice (decline), and price-target request (decline). The "right
answer" is to refuse/redirect, not to answer.
