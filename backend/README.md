# Backend — canonical indexing and Neo4j vectors

Stage B owns canonical text, identity and processing state. Stage C adds real,
model-versioned Neo4j vectors and semantic retrieval through an explicit CLI.
The live corpus build and acceptance record are tracked in `spec.md`. Grounded
graph retrieval and answer dispatch retain their D/E gates. The answer API still
returns **409** with readiness details.

## Run from the repository root

Use the existing virtual environment and `backend/.env`:

```bash
# Read-only migration plan; no app factory or startup writes.
.venv/bin/python -m backend.scripts.migrate --env-file backend/.env

# Explicit additive application migration. Use a NEW private backup filename.
# Stop application writers; backup and migration also share one DB transaction.
.venv/bin/python -m backend.scripts.migrate --env-file backend/.env --apply \
  --backup backend/storage/backups/before-next-migration.db

# Flask, port 5000. Startup does not initialize or migrate the database.
.venv/bin/python -m backend.run
```

The configured application store already received the Stage B migration on
2026-10-18; reapplication is safe and requires another new backup path. New empty
databases need an existing file/store so the default read-only plan can inspect
them. `--apply` initializes the checked-in legacy schema plus additive metadata.

Required existing settings: `TURSO_DATABASE_URL` (or `TURSO_CONNECTION_URL`) and
`TURSO_AUTH_TOKEN`. OCR source credentials are stored encrypted; use their existing
`CREDENTIAL_ENCRYPTION_KEY`. Flask's forwarded identity uses
`BACKEND_INTERNAL_SECRET`. `OLLAMA_EMBEDDING_MODEL` records the intended recipe;
the served digest/dimensions are verified before vector builds and queries. Existing
`NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD` support graph reads and explicit vector builds.
No new dependency or application environment variable was introduced.

## Preview and stage an existing OCR source

Obtain the actual organization/project/source IDs from the existing project and
data-source records. Set the shell placeholders below to those IDs:

```bash
# Preview only: neither database, source progress nor upload files are written.
.venv/bin/python -m backend.scripts.index_source --env-file backend/.env \
  --organization-id "$ORG_ID" --project-id "$PROJECT_ID" --source-id "$SOURCE_ID"

# Same command with --apply stages canonical text/chunks, not vectors or a graph.
.venv/bin/python -m backend.scripts.index_source --env-file backend/.env \
  --organization-id "$ORG_ID" --project-id "$PROJECT_ID" --source-id "$SOURCE_ID" --apply
```

Preview exit 0 means all planned rows passed; exit 2 means per-row failures need
review. Inspect `dry_run`, `failed_count`, hashed record failure IDs and plans.
Creating a source now saves configuration only; it does not start a daemon.
Configured `batch_size` and `max_documents` still apply. Each run starts from the
beginning, so a failed index row cannot disappear behind an old forward cursor.
Duplicate/null source IDs and ambiguous legacy matches are rejected.

Source namespace = endpoint/table/ID-column, independent of credential rotation
and source-configuration UUID. Org/project/source-record mapping is unique.
Exactly one unclaimed legacy filename match preserves its document ID; otherwise
new IDs are deterministic. Generations fingerprint exact text, source metadata
and recipe. Chunk IDs include generation, position and content. Old generations
and legacy vectors remain intact. Canonical Turso text/chunks are **staging input**,
not an alternate retrieval vector store.

## Readiness and provenance

- `GET /api/projects/<project_id>/documents` returns precise `status` and
  `readiness`; historical values are labelled `legacy_status`.
- `GET /api/projects/<project_id>/indexing/status` reports every application
  document in that org/project, generation identities, counts, capabilities,
  integrity results, verification times and retry reasons. The explicit scope is
  `all_application_documents`, not every external OCR record.
- Text-only work reaches `text_ready`; vector/graph flags remain false until
  their real index/retrieval proofs exist. Legacy `ready` is not evidence.
- Source OCR text is unchanged. Native PDF extraction retains exact page offsets;
  flattened OCR without page offsets does not receive invented page numbers.
  Scanned PDFs require existing OCR input; this stage never silently runs OCR.
- Failed/interrupted work is retryable. A live text-stage lease prevents competing
  workers; an expired lease can be reclaimed without letting the old worker publish.

## Neo4j vector indexing and source-reviewed retrieval

Stage C's canonical recipe is `words-v2:350:40:utf8-1800`. The old 350-word recipe
could exceed the served EmbeddingGemma model's measured 2048-token context on
dense OCR. The byte ceiling preserves exact spans without silent model truncation;
long tokens are split with all non-whitespace source characters retained. Prior
source/chunk generations remain intact. Re-stage the source after upgrading the
recipe before building its vector generation.

```bash
# Default plan: read canonical metadata only, no model probe or graph connection.
.venv/bin/python -m backend.scripts.index_vectors --env-file backend/.env \
  --organization-id "$ORG_ID" --project-id "$PROJECT_ID"

# Build/resume real chunk embeddings, leaving the generation unpublished.
# Use batches of 16 on the configured CPU model; 64 exceeded its request timeout.
.venv/bin/python -m backend.scripts.index_vectors --env-file backend/.env \
  --organization-id "$ORG_ID" --project-id "$PROJECT_ID" --apply --batch-size 16

# Diagnostic candidate retrieval, before LLM generation; includes text/spans/scores.
.venv/bin/python -m backend.scripts.index_vectors --env-file backend/.env \
  --organization-id "$ORG_ID" --project-id "$PROJECT_ID" \
  --query "Why did the court spare Ram Narain a return to prison after years on bail?"

# Frozen user-reviewed source labels; output must be a NEW evidence filename.
.venv/bin/python -m backend.scripts.evaluate_vectors --env-file backend/.env \
  --fixture backend/evaluation/stage-c.json \
  --output backend/inventory/reports/stage-c-vector-evaluation-new.json

# Only after scoped integrity, actual retrieval review and rollback checks pass.
.venv/bin/python -m backend.scripts.index_vectors --env-file backend/.env \
  --organization-id "$ORG_ID" --project-id "$PROJECT_ID" --publish

# Availability rollback: revoke this publication; retain all source/chunk/vectors.
.venv/bin/python -m backend.scripts.index_vectors --env-file backend/.env \
  --organization-id "$ORG_ID" --project-id "$PROJECT_ID" --withdraw
```

Indexes use the verified Neo4j 5.26 cosine vector API. Each index label partitions
candidates **before top-k** by org, project, canonical corpus manifest and resolved
model digest. No foreign tenant or stale generation can exhaust a global top-k.
Search requests `max(64, 8*k)` approximate candidates within that partition and
rescores their actual vectors with Neo4j cosine before returning k. This fixes a
measured small-k recall miss; exhaustive exact top-k is not assumed.
Numeric finiteness, 768 dimensions, vector hashes, exact canonical identity/spans,
document containment and ONLINE index configuration are checked before retrieval.
The model digest is checked before and after each embedding request. Neo4j scores
are its measured cosine-index scores in [0,1], not answer-confidence estimates.

`--apply` resumes only matching valid records and stores batch checkpoints/failure
codes in Neo4j `RAGVectorJob`; retries repair malformed vectors. A failed/new build
does not publish itself. Application Turso contains canonical input/control state,
not the new retrieval vectors; legacy `chunk_embeddings` remains untouched.

The canonical manifest advertises the current staged document set. Unstaged
application document IDs are explicitly excluded in CLI output. Current limits:
one retained index per corpus snapshot, full streamed integrity checks on query,
and no cross-snapshot vector reuse/garbage collection. These favor correctness;
Stage G owns higher-throughput incremental operations. No graph/hybrid mode,
answer generation or citation faithfulness is inferred from vector acceptance.

## Stage D — LLM enrichment and evidence-backed graph retrieval

The independent Stage D implementation can be developed/tested while C indexes.
Live enrichment requires **complete, published Stage C vectors**. The current
corpus has not yet passed that gate; no live extraction job has been started.

`GraphExtractor` calls the existing configured Ollama graph model with a strict
JSON schema. Entity names and assertion quotations must occur verbatim in the
canonical chunk. Supported assertions are `CITES`, `INTERPRETS`, `OVERRULES`,
`DISTINGUISHES` and `DECIDED_BY`, with validated endpoint types, explicit predicate
and negation/direction checks. Unsupported output fails visibly; it never becomes
a co-occurrence-derived legal assertion. Model digest, extraction recipe/schema
and inference options identify a separate graph generation.

Exact AIR/year/Supreme-Court/page citations can share an entity across documents.
Other names remain document-scoped; there is no fuzzy name merging or invented
alias resolution. Every mention/assertion keeps all exact chunk/document/span
evidence. Conservative validation can reject legitimate indirect statements;
the model's legal accuracy and corpus coverage still require live source review.
Explicit relation predicates currently have English validators; regional-language
relations require reviewed language-specific rules before coverage can be claimed.

```text
RAGVectorChunk ← FROM_CHUNK ─ RAGEvidence ─ SUPPORTS → RAGEntity:Case/Statute/…
RAGVectorChunk ← FROM_CHUNK ─ RAGEvidence ─ SUPPORTS → RAGAssertion
                                                    ├─ SUBJECT → Document/Case
                                                    └─ OBJECT  → Case/Provision/…
```

`RAGExtraction` records per-chunk attempts, content hash, extractor profile,
validated cached output and precise failure codes. A repeat run reuses validated
extraction rather than calling the model again, and reconstructs its graph evidence
atomically to repair missing/corrupt derived records. Shared evidence from other
chunks is retained. Empty extraction remains explicit and cannot by itself publish
a usable legal graph. `--status` verifies nodes, endpoint links, every quoted span,
type coverage and extraction completeness.
An explicit rebuild revokes that generation's publication before processing;
successful repair/re-extraction must be reverified before republishing.
Reports include at most eight assertion samples with up to three source quotations
each, so a small partial batch can be reviewed before spending on the full corpus.

```bash
# Read-only plan: no model or Neo4j calls.
.venv/bin/python -m backend.scripts.index_graph --env-file backend/.env \
  --organization-id "$ORG_ID" --project-id "$PROJECT_ID"

# AFTER Stage C acceptance/publication: inspect a small enrichment batch first.
.venv/bin/python -m backend.scripts.index_graph --env-file backend/.env \
  --organization-id "$ORG_ID" --project-id "$PROJECT_ID" --apply --max-chunks 4

# Resume a further bounded batch, or use --max-chunks 0 for all remaining work.
# Partial coverage/failures exit 2; inspect the explicit report and retained ledger.
.venv/bin/python -m backend.scripts.index_graph --env-file backend/.env \
  --organization-id "$ORG_ID" --project-id "$PROJECT_ID" --status

# Diagnostic retrieval of connected source evidence, without generating an answer.
.venv/bin/python -m backend.scripts.index_graph --env-file backend/.env \
  --organization-id "$ORG_ID" --project-id "$PROJECT_ID" --query "$QUESTION"

# Only after manually reviewed live graph retrieval and integrity acceptance.
.venv/bin/python -m backend.scripts.index_graph --env-file backend/.env \
  --organization-id "$ORG_ID" --project-id "$PROJECT_ID" --publish

# Roll back graph availability without deleting vectors, text or prior generations.
.venv/bin/python -m backend.scripts.index_graph --env-file backend/.env \
  --organization-id "$ORG_ID" --project-id "$PROJECT_ID" --withdraw
```

Graph retrieval starts from actual Neo4j vector seeds and expands through shared
typed entities or supported assertions. Defaults: 4 seeds, 2 hops, 8 path candidates
per frontier chunk, 24 total passages; hard maxima are 8/2/20/40. Visited chunks
prevent cycles. Added passages carry the exact graph path and evidence spans;
only vector seeds have similarity scores. No expansion returns the explicit
`no_connected_evidence` status instead of masquerading as successful GraphRAG.
All candidates are scoped by graph/vector generation, organization and project.

Existing settings: `GRAPH_LLM_MODEL` (default `smollm2:135m`),
`GRAPH_LLM_TIMEOUT_SECONDS` (60; must be >0 and <=120), `GRAPH_LLM_NUM_PREDICT`
(700; 1–4096), `GRAPH_LLM_NUM_CTX` (4096 minimum), and
`GRAPH_EXTRACTION_MAX_CHUNKS` (0 means all new attempts). No new application
environment variable or dependency was added. Availability of the configured
model has been checked via tags; actual legal extraction quality remains unverified.

Isolated storage/traversal verification uses explicitly supplied disposable Neo4j
and controlled test-only vectors/model responses; it makes **no Ollama requests**:

```bash
STAGE_D_TEST_NEO4J_URI=bolt://127.0.0.1:17688 \
STAGE_D_TEST_NEO4J_PASSWORD="$DISPOSABLE_PASSWORD" \
  .venv/bin/python -m pytest backend/tests/test_evidence_graph.py -q -o addopts='' -p no:cacheprovider
```

Stage D live acceptance is pending: configured-model extraction, reviewed actual
cross-document evidence, failures/coverage, and independent graph retrieval.
Stage E owns answer dispatch/hybrid fusion; Stage F owns frontend integration.

The three marked ceilings are full-source replay, a 60-second text-only lease,
and full text-integrity validation on readiness reads. Before long model jobs or
large-corpus serving, implement durable scheduling, lease renewal and publication
proofs in the relevant later stages.

## Migration recovery and checks

Snapshots under `backend/storage/backups/` are private (0600) and Git-ignored.
They retain all table data, including encrypted credentials and internal vector
metadata, but do not reproduce standalone indexes. They are not a full Turso
service backup. Do not restore internal shadow tables into a running database.

Stage B rollback needs **no data deletion**: stop Stage B workers and redeploy the
previous backend revision, leaving the additive tables intact. Every original
table row was compared with the pre-migration backup after migration, reapply,
preview and Flask checks. A failed migration rolls back atomically; its private
pre-change snapshot remains available. Before later destructive vector cutover,
Stage C must supply its separately verified native backup/restore plan.

```bash
.venv/bin/python -m pytest backend -q -o addopts='' -p no:cacheprovider
.venv/bin/ruff check backend/inventory backend/scripts backend/tests backend/app/db \
  backend/app/__init__.py backend/app/services/rag.py \
  backend/app/services/embedding_service.py backend/app/services/graph_store.py \
  backend/app/services/ingestion_service.py backend/app/services/vector_store.py \
  backend/app/routes/documents.py backend/app/routes/data_sources.py \
  backend/app/routes/graph.py backend/app/routes/query.py --no-cache
```

Live exit evidence: [Stage B report](inventory/reports/2026-10-18-stage-b.md).
