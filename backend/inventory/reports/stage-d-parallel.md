# Stage D — parallel implementation handoff

**Result: implementation and isolated service verification complete; live Stage D
acceptance remains OPEN.** The user explicitly requested independent D work while
C's CPU embedding job runs. This does not waive C/D corpus-quality/publication gates.

## Implemented and verified

| Requirement | Evidence / outcome |
|---|---|
| LLM enrichment on canonical source chunks | `services/graph_extraction.py` and existing `llm_client.py`; strict typed structured output, actual source text in the request, model digest/schema/options recipe, bounded timeout/output/context. HTTP payload checked with mocked transport. |
| Source-backed entities/assertions | Exact verbatim entity/quote occurrences become original document/chunk/generation/character spans. Every occurrence is retained. Endpoint types, active direction, current-judgment attribution, explicit predicates and surrounding sentence negation are validated. Fabricated/clipped/negated/reversed evidence is rejected. |
| Conservative resolution | Exact AIR/year/Supreme-Court/page citations can share identity across documents. Other names are document-scoped; no fuzzy merging of namesakes or invented aliases. |
| Neo4j evidence store | `services/evidence_graph.py`; extractor-versioned graph documents, typed entities, assertion records and individual supporting evidence nodes refer to existing Stage C vector chunks. Per-chunk transaction commits graph facts and extraction proof together. |
| Retry, partial/error status and repair | `RAGExtraction` stores attempts, content/profile hashes, validated output and separate timeout/provider/parse/evidence/storage errors. Repeated runs reuse model output, repair derived records, preserve shared evidence, and report empty/pending/failed chunks. Limited batches remain `graph_partial`. |
| Scoped semantic-seeded graph retrieval | Calls real Neo4j vector search for seeds, then bounded shared-entity/assertion evidence traversal. Fixed budgets, visited chunks, graph/vector/model generation boundaries, tenant checks, path revalidation and passage deduplication. Added graph passages have path evidence and no fabricated similarity score. |
| Graph contribution beyond seeds | Disposable Neo4j test selects one semantic seed and retrieves the second document through a shared exact citation and a supported `CITES` assertion. Both source quotations resolve to their exact canonical substrings. A second tenant with the same citation remains isolated. |
| Integrity/publication/rollback | Complete proof checks cover cached extractions, entity types, assertion endpoints, source documents, every evidence span and actual chunk links. Corrupt spans are detected and repaired without additional model calls. Missing C publication blocks D writes. Graph publication/withdrawal changes availability while retaining data; empty extraction cannot publish a legal graph. |
| Explicit CLI and read-only planning | `scripts/index_graph.py`; plan/apply/status/query/publish/withdraw. Default plan makes no model/Neo4j calls; isolated fixture DB bytes unchanged. Configured read-only plan reconciles **333 documents / 10,417 chunks**, no excluded target documents. |

Assertions are model extraction candidates with explicit source/method evidence,
not independently certified legal conclusions. Quote checks do not replace the
required actual-corpus legal/retrieval review.

## Checks

```bash
.venv/bin/python -m pytest backend -q -o addopts='' -p no:cacheprovider
# 132 passed, 2 opt-in real-service tests skipped

STAGE_D_TEST_NEO4J_URI=bolt://127.0.0.1:17688 \
STAGE_D_TEST_NEO4J_PASSWORD=<disposable-password> \
  .venv/bin/python -m pytest backend/tests/test_evidence_graph.py \
  -q -o addopts='' -p no:cacheprovider
# 3 passed: two unit checks plus the real Neo4j storage/retrieval scenario
```

The disposable Neo4j 5.26.32 test uses explicitly synthetic test-only vectors and
controlled LLM responses. **It tests persistence, provenance, isolation, retries,
rollback and traversal, not embedding quality or LLM legal accuracy.** It makes
no Ollama requests and never targets the configured corpus store. The owned test
container was stopped/removed after checks.

Ruff over inventory/scripts/tests, DB code and touched backend modules: **PASS**.
`git diff --check`: **PASS**. Complete section/new-file diff reviewed before commit.
The integration check caught the driver's managed-transaction restriction on
`Query` objects; writes use a bounded `unit_of_work` transaction instead.

## Configured-store observations

- Source/canonical plan: manifest
  `5f1c67fdcd058eb06d3a7a9f87fbc593b7963dc41e922550cd1360fd8c115689`,
  **333 documents / 10,417 current chunks**; no model calls or graph writes.
- Read-only model tag lookup resolves `smollm2:135m` to
  `9077fe9d2ae1a4a41a868836b56b8163731a8fe16621397028c2c76f838c6907`;
  configured graph timeout is **60 seconds**. No generation request was made.
- Configured Neo4j has **0 `RAGExtraction` records**; Stage D did not mutate it.
- C's vector job remained **processing, 4,704 / 10,417 complete, no error**, with
  its latest checkpoint 33 seconds old at the final observation. This is a progress
  snapshot, not a C acceptance or completion claim.
- Existing application settings are reused; no dependency or application environment
  variable was added. `STAGE_D_TEST_NEO4J_*` variables are opt-in test inputs only.

## Remaining live gates

1. Finish C's full vector build, whole-partition integrity/repeat-build checks,
   approved vector/BM25 passage evaluation and publication/rollback acceptance.
2. After C passes, run a small actual-model D batch and inspect source-backed
   assertion samples before committing to full-corpus enrichment. Availability
   of `smollm2:135m` is verified; its legal extraction quality is **unverified**.
3. Freeze/review an actual cross-document relationship retrieval set, evaluate
   extraction failures/empty coverage and graph contribution beyond semantic seeds,
   then record actual graph-mode evidence and integrity/publication/rollback results.
4. Do not claim regional-language relationship coverage from the current English
   explicit-predicate checks. Review/add supported language rules as required by
   the advertised corpus; unsupported statements must not become legal assertions.

Current marked operational limits: full graph-proof checks on reads, cached graph
write replay for repair, conservative citation-only cross-document resolution and
English predicate validation. Stage E answer/hybrid dispatch and Stage F UI remain
their own work. No live GraphRAG-ready or answer-quality claim is made here.

## Commands / handoff

See `backend/README.md` for graph operations and publication prerequisites.
Application launch from repository root remains:

```bash
.venv/bin/python -m backend.run
```

Commits: C.3a `071b2b4`; D.1 `a28c227`; D.2 hash is recorded in the user handoff.
Unrelated untracked `backend/test.md` is preserved and excluded.
