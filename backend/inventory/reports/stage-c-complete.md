# Stage C — verified and published vector retrieval

**Stage C COMPLETE for the advertised canonical corpus.** Scope: organization
`z94VqUBs7dCK6PdESE7nYmzlfQXL2rFl`, project
`proj_c1317127b1c4413596c54b21a633a38f`, **333 documents / 10,417 chunks**.
This closes the vector stage, not Stage D graph enrichment, Stage E answer
faithfulness or general legal-domain accuracy.

## Exit criteria and actual evidence

| Criterion | Actual evidence / outcome |
|---|---|
| Real model, dimensions and provenance | Ollama `embeddinggemma:latest`, digest `85462619ee721b466c5927d109d4cb765861907d5417b9109caebc4e614679f1`, measured finite/nonzero 768D output; revision checked around embedding requests and again before publication. |
| Real Neo4j vectors and ONLINE index | Current partition `02336a1d1a5a22883559a3cfedd22ecdb3b39247342d3c99178e44a1b99f3032`; index `ragv_02336a1d1a5a22883559a3cfedd22ecdb3b39247342d3c99178e44a1b99f3032` ONLINE, dimension-compatible cosine configuration. |
| Whole advertised scope coverage/integrity | **10,417/10,417 valid vectors**, **333 source-document nodes**, **0 orphan document nodes**. Complete numeric/hash/model/generation/tenant/chunk-ID/span/document-containment verification passed; no missing or unexpected current-partition chunk IDs. |
| Resume and idempotency | Interrupted work resumed from persisted checkpoints. Explicit repeat build reported **10,417 reused / 10,417 verified**, no new embeddings except the transient compatibility probe and no duplicate generation. |
| Source/legacy preservation | **333 source mappings**, **666 retained text generations**, **17,892 retained canonical chunks** (old + current). **80** prior incomplete-recipe Neo4j vectors retained in their separate partition. Legacy Turso vectors in this project remain **0**; no provenance-unknown vector copy, source re-OCR, destructive replacement or relabeling. Private pre-change backup remains `backend/storage/backups/stage-c-before-2026-10-22.db`. |
| Reviewed paraphrase retrieval before answer generation | `stage-c-vector-evaluation-v3-01.json` **passed** with user-reviewed original source spans; ranks below. A supporting semantic-only passage appears at vector rank 3 while BM25 top 8 misses it. No answer LLM was called. |
| Publication and rollback before final cutover | Publish → complete published search and readiness verification → withdraw → published reads refused and vector capability false → **all 10,417 vectors retained** → canonical/model recheck → republish. Final actual readiness: `vector_ready`, text=true/vector=true/graph=false. |

Canonical manifest:
`5f1c67fdcd058eb06d3a7a9f87fbc593b7963dc41e922550cd1360fd8c115689`.
The same source/model/corpus manifest was verified again before final publication.
The job's `verified_unpublished` value records its last **build** outcome;
`RAGVectorPublication` and fresh readiness checks are authoritative for current
published availability.

## Source-reviewed vector smoke results

Fixture: `backend/evaluation/stage-c-v3.json`, frozen as `692c5b9` before its
validation run. k=8. Each of the four positive cases has Recall@8=1.

| Case | Expected-source rank | Reciprocal rank | BM25 expected hit in top 8 | Outcome |
|---|---:|---:|---:|---|
| Exact judgment heading/date | 1 | 1 | 1 | PASS |
| Original handwriting-opinion paraphrase | 7 | 1/7 | 1 | PASS; no semantic-only advantage claimed |
| Sentence delay/bail reasoning | 1 | 1 | 1 | PASS; no semantic-only advantage claimed |
| Independent authorship/verification paraphrase | 3 | 1/3 | 0 | PASS; measured semantic-only advantage against declared BM25 baseline |
| Unanswerable control | No supporting label | N/A | 0 | Retrieval candidates only; no answer generated. Actual abstention remains Stage E. |

This is a **pooled, human source-reviewed smoke set from one judgment**, not a
held-out benchmark or a claim that every judgment/question is correctly answered.
Original v1/v2 fixtures and all failed reports remain committed. The review history
is explicit: narrow headnote-only labels initially rejected relevant original
judgment-body passages; the user reviewed/approved the actual passages in v2/v3.
Queries and top-8/BM25 criteria were preserved for those corrections. Do not report
the earlier frozen headnote-only evaluations as passing.

The production change was separate: a genuine HNSW k=8 recall miss for an exact
rank-7 passage was fixed with in-partition `max(64,8*k)` candidate retrieval and
actual cosine rescoring. See `stage-c-retrieval-investigation.md`.

## Commands and checks

```bash
# Repeat/resume: all 10,417 matching vectors reused; does not generate an answer.
.venv/bin/python -m backend.scripts.index_vectors --env-file backend/.env \
  --organization-id z94VqUBs7dCK6PdESE7nYmzlfQXL2rFl \
  --project-id proj_c1317127b1c4413596c54b21a633a38f --apply --batch-size 16

# Reviewed vector evaluation; always use a NEW report path.
.venv/bin/python -m backend.scripts.evaluate_vectors --env-file backend/.env \
  --fixture backend/evaluation/stage-c-v3.json \
  --output backend/inventory/reports/stage-c-vector-evaluation-v3-new.json

# Availability operations verified against the configured store.
.venv/bin/python -m backend.scripts.index_vectors --env-file backend/.env \
  --organization-id "$ORG_ID" --project-id "$PROJECT_ID" --publish
.venv/bin/python -m backend.scripts.index_vectors --env-file backend/.env \
  --organization-id "$ORG_ID" --project-id "$PROJECT_ID" --withdraw
```

Configured-store checks additionally measured 333 document nodes/zero orphans,
validated all vectors before/after withdrawal, checked first expected search rank 1,
and verified fresh API readiness toggled vector true → false → true without losing
vectors. Authorized canonical passage GET returned 200 with exact hash and
`Cache-Control: no-store`; before publication, vector POST returned
409/`vector_not_ready`, **0 model calls**, and query-run count **0 → 0**.

Backend suite **177 passed, 3 opt-in skipped**; scoped Ruff, Black and diff checks
passed. No new dependency/application environment variable. The unrelated Black
development-dependency changes under `sc-dataset/` are excluded from stage commits.

## Next work

Live Stage D enrichment is now eligible under the user's explicit continuation.
Start with a bounded actual-model batch and review source-backed extraction before
scaling. Graph/hybrid and real grounded-answer acceptance remain unchecked in
`verification-return.md`. Any changed corpus/model/chunker/index condition reopens
the affected verification gate rather than inheriting this result silently.
