# Stage C — live retrieval investigation

**Acceptance remains OPEN; no publication or live graph enrichment.** All 10,417
vectors are physically verified, but the frozen retrieval evaluation must not be
reported as passing while a required case fails.

## Preserved baseline and root cause

`stage-c-vector-evaluation-01.json` records the original four frozen queries.
Exact case lookup passed; both headnote-labelled paraphrase cases missed top 8.
The corpus/model/IDs are the unchanged `backend/evaluation/stage-c.json` generation.

Read-only diagnostics compared the expected passage's exact Neo4j cosine score
against **all 10,417 in-partition vectors**, and separately requested 64 HNSW
candidates. No vectors, source text, labels or model revisions were rewritten.

| Case | Exact expected-passage rank / score | HNSW rank when requesting 64 | Finding |
|---|---|---|---|
| `semantic-paraphrase` | 7 / 0.6943429112434387 | 7 | The original k=8 approximate call missed an actual exact-top-8 passage. Candidate recall is the defect. |
| `sentence-delay-paraphrase` | 21 / 0.7133813500404358 | 23 | The expected headnote is not exact top 8; the same judgment's actual reasoning passage is rank 1. This is a separate relevance-label issue. |

## Candidate recall correction

Shared `Neo4jVectorStore.search` now requests `max(64, 8*k)` HNSW candidates
**inside the existing org/project/model/corpus partition**, computes actual
`vector.similarity.cosine` for those candidates and returns the best k. The public
k limit remains 100, so the candidate request is bounded at 800. This is exact
rescoring of approximate candidates, not a claim of exhaustive exact search.

`stage-c-vector-evaluation-02.json` reruns the **unchanged original queries and
labels** after that correction:

- Exact case: expected passage rank **1**, Recall@8 **1**.
- Generic semantic paraphrase: expected passage rank **7**, Recall@8 **1**.
- Sentence-delay expected headnote: still absent from top 8; **FAIL retained**.
- Unanswerable control: no answer generation, not an answer-abstention quality pass.

Backend checks: **177 passed, 3 opt-in skipped**; targeted Ruff, Black and diff
checks pass. Regression covers candidate budgets at k=1/8/100 and retains foreign
scope/stale-result rejection. The live rerun is the actual-service recall regression.

## Sentence-delay label problem — review required, not silently fixed

The question asks why Ram Narain was spared a return to prison after years on
bail. Both vector retrieval and the separately measured BM25 baseline return the
actual same-judgment reasoning passage first:

- Chunk: `chk_ffd0238ef0ad4b6b0a2fc8924f97bfcd6571ac8f2b0d520add8c523d41280248`.
- Document: `doc_052e9d2002414127b7e055f274ab62ad`.
- Generation: `gen_ded0010c3b4ad85f1b34d501217036585852cde51c7061c9a9b3c16b06ef06ea`.
- Original OCR character span: **16785–18481**.
- Content hash: `1f9cab4c2e93d9e124b70e9cbfe0cd17dbdc8fe4f76edd2ff8f98624286a2505`.
- Source: `data/pdf/year=1973/english/1973_3_911_917_EN.pdf`.

It states that the proceedings lasted more than eight years, that bail was granted
in January 1970, and that sending the appellant back after so many years would
be harsh. The frozen label instead names the earlier duplicate headnote at
3110–4875. Returning the reasoning passage is useful evidence, but it is **not a
pass against that original frozen headnote-only criterion**. Because BM25 also
finds the reasoning passage first, this case cannot substantiate a genuine
semantic-only/BM25-miss claim.

Any revised relevance label or replacement semantic-only query needs an explicit
source/test review and a new versioned fixture before evaluation. Preserve the
original fixture and both failed reports. Do not hard-code a case/expected chunk
into production ranking or change queries/labels after the fact to claim a pass.
