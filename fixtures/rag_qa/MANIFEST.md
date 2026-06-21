# RAG Q&A fixture manifest

- records: 13 (10 positive, 3 negative)
- workflow: rag_qa (financial path, frozen single-turn isolated generation)
- input per record: `{question, context, expected_facts[], category}`

## ⚠️ DRAFT — figures need Elroy's verification

The J$ figures in `context` are **illustrative drafts**, not pulled from real statements.
They are internally coherent (each record's `expected_facts` is answerable from its
`context`, and YoY/percentage claims match the numbers), so the benchmark is *valid* as
written — it tests whether a model faithfully uses the provided context. **But before this
becomes authoritative ground truth, replace/verify the figures with real JSE data** (from
the financial statements or BigQuery). A wrong figure here silently penalizes every model.

Companies referenced (real JSE symbols): NCBFG, GK, JBG, SGJ, CAR, WIG, JMMBGL.

## Validity rule

Every `expected_fact` must be answerable from that record's `context`. Holds by construction
for all 13 records; re-check after any figure edit.

## Negative cases

3 records test the production safety/scope rules: off-topic request (decline + redirect),
personalized buy/sell advice (decline), and price-target request (decline). The "right
answer" is to refuse/redirect, not to answer.
