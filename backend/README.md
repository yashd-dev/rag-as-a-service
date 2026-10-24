# Backend — canonical indexing and Neo4j vectors

Stage B owns canonical text, identity and processing state. Stage C is verified
and published for **333 canonical documents / 10,417 real Neo4j vectors**. Its
reviewed vector smoke set, integrity, reuse and availability rollback passed;
see `inventory/reports/stage-c-complete.md`. Query/source API implementation is
present. Graph enrichment and real grounded-answer quality retain their D/E
acceptance gates; unavailable graph/hybrid modes return **409**, not vector fallback.

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
No new package dependency is required. Optional `GRAPH_EXTRACTION_STRATEGY`
selects an opt-in graph extractor; its default remains `full_legal`.

## Shared legal corpus — Stage H.1 backend access

The additive migration now also creates `shared_corpora` (the platform's `legal`
registration) and `project_corpus_references` (workspace-local corpus references).
Existing projects remain private unless explicitly registered or created as a
reference. Neither migration nor registration copies, re-labels or re-embeds data.
Run the migration above before deploying this backend; Flask startup remains
write-free. This migration has **not** been applied to the configured live store.

Platform operators with the existing backend database credentials may register
the accepted legal project. Verify its actual organization/project IDs and source
scope against the Stage C inventory first. This operation makes that project's
source content available to every authenticated workspace through a local
reference; it does not certify or publish its retrieval generations.

```bash
# Read-only plan; these variables must identify the verified legal scope.
.venv/bin/python -m backend.scripts.register_shared_corpus --env-file backend/.env \
  --organization-id "$ORG_ID" --project-id "$PROJECT_ID"

# Stop application writers first. Requires a NEW private backup filename.
.venv/bin/python -m backend.scripts.register_shared_corpus --env-file backend/.env \
  --organization-id "$ORG_ID" --project-id "$PROJECT_ID" --apply \
  --backup backend/storage/backups/before-legal-registration.db
```

Registration is idempotent for the same target and refuses retargeting. It has no
HTTP endpoint: workspace roles and caller-supplied organization headers cannot
authorize platform maintenance. Source/index maintenance CLIs remain operator
tools requiring backend database/provider/Neo4j credentials, which must not be
distributed to workspace users.

Through the existing trusted-session API:

- `POST /api/projects` accepts `{"name":"Legal","corpus_source":"legal"}` to
  create a local reference. `corpus_source` defaults to `private`; legal creation
  returns `503 shared_corpus_unavailable` until an operator registers the source.
- Project list/detail/create responses include `corpus_source` and `read_only`.
  Legal references default to vector mode; graph/hybrid still require independent
  published readiness. Requests cannot select an arbitrary canonical target.
- Query, passages, documents, readiness and graph reads use the authorized
  canonical scope. Citation URLs, conversations and query runs retain the local
  project/workspace; platform credentials and uploader identity are not copied.
- Upload, document deletion and source attachment return `403
  shared_corpus_read_only`, including for owners in the source workspace.
  Deleting a reference detaches only that reference. Deleting the canonical
  registered project is denied. Database foreign keys/triggers also prevent
  canonical project deletion, reference retargeting and document ingestion into
  references; foreign keys must remain enabled for direct operator connections.
- Forwarded identities fail closed when `BACKEND_INTERNAL_SECRET` is unset.
  These internal routes are not the future public Bearer-key API.

Dashboard legal/private creation controls and live two-workspace acceptance remain
the next Stage H increment. H.1 tests use actual local libSQL/canonical text with
controlled model/vector/graph boundaries; they do not certify live providers.

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
  --fixture backend/evaluation/stage-c-v3.json \
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
Live enrichment requires **complete, published Stage C vectors**. The advertised
333-document vector corpus has passed that gate. Actual-model graph enrichment
still needs a bounded first batch and source review before full-corpus processing.

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

### Opt-in small local citation verifier

`citation_candidates` is an additive, citation-focused strategy. The existing
`full_legal` extractor and active model settings remain the default. This mode
recognizes exact AIR/year/SC/page reference strings from canonical text; it keeps
all matching mention spans, and asks the local model only whether a bounded,
source-validated affirmative `CITES` candidate is supported. Names and quotations
come from source text, not model generation. Thinking is off and each verifier
response is capped at 64 tokens. Chunks without eligible candidates make no text
generation calls; `citation_verifier_calls` reports actual verifier attempts.

```bash
# Read-only process-local plan; does not edit backend/.env or load a model.
.venv/bin/python -m backend.scripts.index_graph --env-file backend/.env \
  --organization-id "$ORG_ID" --project-id "$PROJECT_ID" \
  --strategy citation_candidates --model qwen3:1.7b

# Bounded integration only; first source chunks may have no eligible citations.
.venv/bin/python -m backend.scripts.index_graph --env-file backend/.env \
  --organization-id "$ORG_ID" --project-id "$PROJECT_ID" \
  --strategy citation_candidates --model qwen3:1.7b --apply --max-chunks 4
```

Persistent opt-in, only after source/coverage review, uses the new optional
`GRAPH_EXTRACTION_STRATEGY=citation_candidates` plus existing
`GRAPH_LLM_MODEL=qwen3:1.7b`. CLI overrides take precedence for that process and
leave the settings file intact. The public query/source API contract is unchanged;
published graph readiness/diagnostics identify its strategy/profile.

Citation generations record strategy, model digest, pattern/cue/prompt/schema
hashes and validator version. Cache replay rederives the exact source plan;
unexpected entities, quotations or relations fail validation. Exceeding eight
distinct candidates is an explicit retry/coverage error, not silent truncation.

Coverage is intentionally limited to these exact citation forms and affirmative
English cues. Citation mentions alone do not claim a legal stance. This mode does
not fix broader judge/statute/concept NER, OCR variants or general graph quality.
The initial narrow local diagnostic classified two actual reference windows and
a negated control correctly; full corpus coverage, source review and graph/hybrid
retrieval acceptance remain required in `inventory/reports/verification-return.md`.

## Stage E — grounded query and source API

The backend query/source implementation and isolated C/D/E service fixtures pass;
real generated-answer/citation quality remains an open live acceptance gate.
See `inventory/reports/stage-e-implementation.md` and the mandatory
`inventory/reports/verification-return.md` checklist.

- `POST /api/projects/<project_id>/query` accepts `{message, mode?, conversation_id?}`.
  Message limit: 1024 UTF-8 bytes. Modes execute their actual retrieval paths;
  graph/hybrid require published graph evidence and never silently become vector-only.
- Response includes `status` (`answered` or `insufficient_evidence`), `answer`,
  `query_run_id`, cited `sources`, distinct context `citation_candidates`, stable
  `used_citation_ids`, actual provider/model/fallback and retrieval diagnostics.
  Inline `[S1]` labels map to stable citation IDs in the source objects.
- `GET /api/projects/<project_id>/passages/<chunk_id>` resolves exact authorized
  canonical text with source hash/spans/pages and `is_current_generation`.
  Historical citations are labeled; flattened OCR receives no invented page numbers.
- Both routes require configured `BACKEND_INTERNAL_SECRET` and the existing trusted
  forwarded secret/user/org headers. Use a trusted server integration; these routes
  return 503 if that backend authentication is unconfigured. Responses are no-store.
- Invalid payloads return 400; unavailable modes/stale generations 409; foreign
  projects/conversations/sources 404; provider, generation or source-integrity
  failures return safe 503 diagnostics. Failed/insufficient work is never recorded
  as a successful completed answer.

Platform generation uses existing `PLATFORM_LLM_*` configuration, with existing
`OLLAMA_BASE_URL` / `FALLBACK_LLM_MODEL` fallback. Provider/model/fallback are reported;
the selected-credential/BYOK path is not advertised as implemented. Evidence is
untrusted JSON under a whole-passage budget, not instructions to the model. Known
source-reference validation does not substitute for human claim/citation review.

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
