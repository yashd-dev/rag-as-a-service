# Implementation Specification & Completion Checklist
## Agentic RAGaaS — Supreme Court Judgments

> **Purpose:** Evidence-based audit and implementation contract for a first-party RAG backend and frontend. This revision plans implementation; it does not implement or certify the RAG pipeline. Checkboxes record only the specific work proven by their evidence.
>
> **Audit date:** 2026-10-18. **Scope:** `backend/` and `web/` (the actual Next.js frontend; no `frontend/` directory exists). Other service folders were not audited. **Required target:** Neo4j stores both the knowledge graph and real retrieval embeddings. Turso remains the application/control-plane database and an existing OCR input source. **LightRAG is conceptual reference only:** never import, install, invoke, wrap, vendor, or depend on its repository/modules/server.

---

## 0. Operating Rules for the Coding Agent

- [x] Inspect scoped source, `web/AGENTS.md`, dependencies, environment examples, schemas, test availability, and Git status/diff before editing. Evidence: Section 2; initial Git status contained only this untracked checklist, with no tracked diff.
- [x] Identify actual integration paths from scoped code; distinguish code presence from runtime verification. Evidence: Section 2.
- [x] Produce an initial audit under **Section 2** using `Implemented`, `Partial`, `Missing`, `Broken`, or `Unverified`.
- [ ] Preserve existing user work. Do not overwrite, reset, drop, or re-ingest production data without an explicit, safe migration plan.
- [ ] Follow the target architecture: **Next.js (`web/`), Flask (`backend/`), Turso/libSQL for application metadata and OCR input, Neo4j for graph + vector retrieval**. Migrate existing Turso vectors safely rather than preserving that placement as the final design.
- [ ] Keep implementation and tests under `backend/` and `web/`; this root checklist is the planning-document exception. Existing `ai.*` imports are an identified scope dependency to replace with backend-owned functionality. Do not investigate or modify unrelated services to implement this plan.
- [ ] Enforce zero LightRAG dependency: no Python/JS imports, package dependency, subprocess/CLI invocation, HTTP request to a LightRAG service, repository path manipulation, copied/vendor implementation, or re-exported adapter. Implement the ideas independently in backend-owned modules.
- [ ] Do not invent table names, columns, API routes, environment variables, model IDs, or storage paths. Discover them in the repository and document the real names here.
- [ ] **Execute only one stage per run.** After completing its implementation, update the checklist, run its relevant tests/checks, inspect the Git diff (including newly created files), and report results against every exit criterion. Stop and hand off; do not automatically begin another stage in the same run. A subsequent run may begin the next stage only after the current stage's exit criteria pass.
- [ ] **Complete one section at a time within the active stage, then commit before continuing.** Select one bounded checklist section/subsection or explicitly identified subset belonging to that stage; record its scope and acceptance criteria before editing. Finish its implementation, update checklist evidence, run relevant checks, review the diff, and create a successful Conventional Commit before starting the next section. Do not batch unrelated sections into one large implementation or commit. Cross-cutting sections may be completed incrementally across stages; never expand the active stage merely to check off an entire numbered section.
- [ ] **Use Conventional Commits for each verified increment:** `<type>(<scope>): <description>` (for example, `feat(inventory): add read-only corpus report`, `fix(retrieval): reject incompatible vectors`, or `docs(checklist): record inventory evidence`). Before committing, inspect `git status`, `git diff` (including staged/new-file content), and `git log --oneline -10`; stage only the intended section's changes and its checklist evidence. Exclude secrets and unrelated user work. Record the commit hash and check results in the handoff report; avoid an extra commit solely to insert its own hash into this file.
- [ ] **A failed check or commit blocks the next section.** Fix the failure and retry without bypassing hooks, amending history, force-pushing, or creating empty commits. If blocked, report the unfinished section and stop advancement. A verified no-change section needs evidence and a reported no-change outcome, not an empty commit. Successful section commits permit the next section only within the current stage; after the final section, apply the stage exit gate and stop for handoff.
- [ ] **Never proceed with a failed migration, unverified embedding dimensions, or an incomplete data inventory.** Missing credentials or evidence block the gate; they do not waive it. Migration additionally requires the recorded inventory review in Section 2.7.
- [ ] Never mark a checkbox complete without evidence: code location, test, command output, or a reproducible manual verification.
- [ ] If blocked by missing credentials, inaccessible services, unavailable models, or unclear product decisions, document the blocker and continue only independent work within the active stage. Do not advance stages or fake successful integration.
- [ ] Update this Markdown checklist as work progresses. Keep completed items checked and leave unfinished or unverified items unchecked.
- [ ] At the end, provide a summary of changes, tests run and their outcomes, remaining gaps, required environment variables, and exact commands to run the application.

### Non-negotiable correctness rules

1. **A graph is not GraphRAG just because it renders nodes and edges.**
2. **A graph of document-content nodes without embeddings does not satisfy the semantic graph-retrieval requirement.**
3. **Do not silently substitute graph visualization, keyword search, or placeholder vectors for real embeddings and retrieval.**
4. **Do not generate fake embeddings, hard-code similarity scores, or report successful semantic retrieval without a real embedding-generation and similarity-search path.**
5. **Do not claim the existing corpus is indexed until the audit verifies document/chunk counts, embedding coverage, graph coverage, and retrieval behavior.**
6. **Existing OCR text is an input to the indexing pipeline; do not repeat OCR unnecessarily or discard source/page metadata.**
7. **Neo4j must actually hold and search real embeddings; graph visualization plus vectors in another store does not meet the requested target.**
8. **A reported retrieval mode must execute that mode. Graph failures, chunk-only indexing, missing embeddings, and partial extraction must not masquerade as complete GraphRAG.**

---

## 1. Project Context and Scope

### Confirmed from the current project brief

- [x] The project is an Agentic Retrieval-Augmented Generation as a Service (RAGaaS) platform.
- [x] The initial domain corpus includes Indian Supreme Court judgments.
- [x] The user identifies existing OCRed judgment content as input to reuse; its live schema, location, and coverage remain unverified.
- [x] The system is intended to support document processing, chunking, embeddings, vector/semantic retrieval, knowledge graphs/GraphRAG, citations, and an agentic query workflow.
- [x] Source confirms **Next.js 16.3.3 / React 19.2.8** in `web/`, **Flask** in `backend/`, **Turso/libSQL** application tables/vectors, and calls to a **Neo4j** graph store.
- [x] Scoped static implementation status and feasible baseline checks are recorded below. Live corpus/index correctness is not verified.

### Binding design decisions

- Neo4j is the final retrieval store for chunk vectors and typed graph evidence; no Turso-only semantic-search completion claim.
- Preserve Turso application records, authentication, encrypted credentials, conversations, and query runs. The OCR-source Turso connection can be different from the application database.
- Independently implement chunking, embedding calls/validation, extraction, graph storage, retrieval, and grounding in `backend/`; the current dependency on sibling `ai/` does not meet the requested ownership boundary.
- LightRAG-inspired ideas may include chunk/entity/relation indexing and local/global evidence retrieval. No particular named algorithm, community pipeline, or UI resemblance is proof of completion. Implement chunk-vector seeds + bounded evidence-backed graph expansion first; defer entity/relation/community vector indexes until their retrieval use is specified and tested.

### Scope priority

**P0 — correctness of the existing Supreme Court corpus**
1. Read and inventory the existing corpus safely, recording and reviewing live counts, dimensions, model provenance and migration eligibility before writes.
2. Establish stable document/chunk identities and make real embeddings plus semantic retrieval work correctly in Neo4j.
3. Build a provenance-backed knowledge graph and working semantic-seeded graph retrieval.
4. Integrate actual vector, graph and hybrid retrieval modes into Flask and the Next.js playground.
5. Verify citations, indexing/retry reliability and regressions using a manually reviewed set of actual Supreme Court source passages.

**P1 — production-quality behavior**
- Source citations with judgment metadata and page/section references where available.
- Incremental, idempotent indexing.
- Error handling, observability, and data-integrity checks.
- Authentication/authorization and project/tenant boundaries, if already part of the application scope.

**P2 — broader platform capabilities**
- Agentic routing, reranking, conversational memory, configurable providers/BYOK, S3 ingestion, web search, public API/streaming, embeddable assistant, and broader security evaluations. Hybrid retrieval is P0, not deferred.
- Do not let P2 features distract from an incomplete P0 pipeline.

**Scope control — applies to every later checklist and completion gate:** Authentication redesign/role hardening, BYOK wiring, conversational memory, S3 integration, broad deletion/file-retention reconciliation, frontend graph-layout/visualization improvements and operational platform expansion are deferred unless a concrete defect blocks one of the five P0 objectives. Existing tenant isolation, safe migration/rollback, source provenance, truthful readiness and reliable indexing remain required. Record a promoted blocker, its evidence and the minimum fix within the active stage; do not start a separate workstream. Later sections retain deferred findings for traceability, not as permission to expand the current stage or as unconditional P0 completion requirements.

---

## 2. Repository and System Audit — 2026-10-18 Baseline

Do not infer completion from the UI. Inspect source code, schemas, data, and execution paths.

| Area | Status | Evidence / actual file, table, command, or observation |
|---|---|---|
| Repository structure and instructions inspected | Implemented | Inspected `backend/` and `web/`; frontend instructions in `web/AGENTS.md` and `CLAUDE.md`. No `frontend/`. No scoped test files found; no tracked initial changes. |
| Next.js app starts and builds | Partial | `web/package.json`: Next 16.3.3, React 19.2.8, Bun 1.3.14. Lint, typecheck, production build pass; authenticated runtime/browser flows not exercised. |
| Flask app starts and exposes documented routes | Unverified | Factory `backend/app/__init__.py:create_app`; entry `backend/run.py`. Startup writes schema and updates project metadata, so it was not invoked against configured data during this audit. Routes traced statically below. |
| Frontend-to-backend API configuration works | Partial | `web/lib/backend.ts:11–46` forwards server-side identity/internal-secret headers to `BACKEND_URL`; no explicit fetch timeout/runtime response validation. No live round trip tested. |
| Turso connection and schema verified | Partial | `backend/app/db/{connection.py,schema.sql}` traced. Read-only local snapshot inspected; remote connection/schema not verified. |
| Existing OCR text/table(s) identified | Partial | Configurable source adapter exists. UI defaults `pdfs.path`, `ocr_text`, `ocr_status='done'`, `url` are assumptions, not verified live schema. `fetch_batch` selects only source ID + text. |
| Existing S3 objects/bucket usage identified | Partial | `data_source_service.py` stores bucket/endpoint/prefix and encrypted keys. No S3 listing/download ingestion path found in scoped backend. Uploads use local filesystem; boto3 dependency alone is not integration. |
| Document IDs and source metadata identified | Partial | `repository.py` generates UUID-prefixed IDs; `documents` has only ID, project/org/uploader, filename, status, timestamps. OCR source ID is put into filename; no durable source-record uniqueness or legal/page metadata columns. |
| Chunking implementation identified | Partial | `ingestion_service.py:85–112` calls external `ai.ingestion.chunker`; embedding chunks and cleaned graph chunks are separate passes. Actual chunker behavior not audited outside scope. IDs for vectors are `chunk:{document_id}:{chunk_index}`. |
| Embedding model/provider identified | Partial | `embedding_service.py` calls external `EmbeddingGemmaProvider` with Ollama URL/model (default `embeddinggemma`). Project metadata is forced to `huggingface` / `google/embeddinggemma-300m`, independent of UI choice. Real provider validation/output unverified. |
| Embedding storage format and dimensions identified | Implemented | Declared `chunk_embeddings.embedding F32_BLOB(768)`, write `vector32(JSON)`, native libSQL vector index declaration. Model/dimension/version not stored per vector. Declaration is not measured coverage. |
| Existing embedding coverage measured | Unverified | Local snapshot has no `chunk_embeddings` table; remote vectors/counts not measured. Do not infer empty production corpus. |
| Graph schema and graph construction code identified | Partial | `ingestion_service.py` invokes `ai.graph.store.Neo4jGraphStore.ensure_constraints/ingest_document`. Driver dependency/config present. Actual graph labels, keys, constraints, edge types, embeddings and provenance cannot be established from the scoped caller. |
| Graph node/edge counts and types measured | Unverified | Status/visualization routes delegate externally; no read-only Neo4j diagnostics run. |
| Graph nodes linked back to source chunks/documents | Unverified | Document/chunks are passed to the external store, but extraction aggregates entities/relations without attaching the originating graph-chunk ID in this caller. Exact source linkage not proven. |
| Vector/semantic retrieval path identified and tested | Partial | `query.py:31–52` → query embedding → `TursoVectorStore.search` → SQL cosine distance ordered per project. It does not use Neo4j or an explicit ANN query; no real semantic query verified. |
| Graph retrieval path identified and tested | Missing | Query endpoint never calls a graph store/traversal. Accepted `mode` is recorded/echoed without dispatch. Visualization endpoints do not satisfy retrieval. |
| Query generation path and citations identified | Partial | External `build_grounded_prompt` + platform OpenAI-compatible LLM then Ollama fallback. `sources` returns chunk/document/file/score only; no passage, legal/page reference, answer-span mapping, or source-view endpoint. |
| Tests, lint, typecheck, and build commands identified | Partial | Frontend commands pass (Section 2.4); scoped pytest collects zero tests. Tests elsewhere deliberately not audited. |
| LightRAG integration within scope | Partial | No `lightrag` import or package dependency found in backend/web manifests or backend Python; `graph-client.tsx` only advertises “LightRAG-style” UI. Full transitive independence is unverified while RAG imports live outside scope. |
| Scope-independent backend RAG ownership | Missing | Backend imports graph extraction/store/visualizer, chunker/OCR client, embedding provider, retrieval schema and grounding from `ai.*`. Replace with first-party backend modules; do not assume those external implementations are correct. |

### 2.1 Entry points, storage and data facts

- **Frontend:** App Router `web/app/layout.tsx`, `app/page.tsx`; application pages `/dashboard/document`, `/dashboard/graph`, `/dashboard/playground`, `/dashboard/llm`. Better Auth uses `lib/auth.ts`, `lib/auth-schema.ts`, `lib/dashboard-context.ts`, and `db/index.ts` (Drizzle/libSQL). `db/schema.ts` contains sample users/posts; `migrations/0000_purple_karnak.sql` instead defines auth tables (`account`, `invitation`, `member`, `organization`, `session`, `user`, `verification`). Neither proves the deployed schema; do not confuse either with backend RAG tables.
- **Backend:** `python -m backend.run` from repository root; factory registers eight blueprints. `Config` loads `backend/.env` with `override=True`. No `.env` values were printed or copied into this report.
- **Application Turso:** `TURSO_DATABASE_URL` or fallback `TURSO_CONNECTION_URL`, plus `TURSO_AUTH_TOKEN`. `connect()` requires both; the checked-in SQLite file is not an automatic fallback. `init_db()` executes schema and migrations on startup; migration unconditionally rewrites all project embedding metadata without inspecting actual vectors (`connection.py:35–39`).
- **Source Turso:** stored separately as `data_sources.endpoint_url` plus encrypted token in `encrypted_secret_access_key`; `prefix` is overloaded JSON containing source column mapping, project ID, cursor, counters and ingestion state. Source credentials need the same persistent encryption key across restarts.
- **Declared application tables:** `projects`, `provider_credentials`, `data_sources`, `documents`, `chunk_embeddings`, `conversations`, `messages`, `query_runs`. Chunk text currently lives in `chunk_embeddings.content`; there is no canonical full-OCR application table in this schema.
- **Local read-only observation:** opened `backend/storage/backend.db` using SQLite `mode=ro`. Seven tables (`conversations`, `data_sources`, `documents`, `messages`, `projects`, `provider_credentials`, `query_runs`) each contain **0 rows**; `chunk_embeddings` is absent. This is a historical/local snapshot, not evidence about configured remote Turso or the Supreme Court corpus.
- **Live document/chunk/valid-vector counts:** unknown. **Neo4j labels, node/edge counts, embedding counts, dimensions in use, index readiness and provenance coverage:** unknown. These require explicit read-only diagnostics before migration.
- **OCR mapping:** defaults are `pdfs`, ID `path`, text `ocr_text`, status `ocr_status='done'`, source URL `url`. `url_column` is saved but never selected in `fetch_batch`; PDF extraction joins page texts and loses structured page boundaries. Actual case/date/court/bench/paragraph columns must be discovered through the configured source connection, not another service's code.

### 2.2 Actual HTTP contract (static audit)

All paths below are Flask paths; except health they use `auth_or_error` and forwarded identity context. Error handling is route-specific, not a unified API contract.

| Path | Actual behavior / contract gap |
|---|---|
| `GET /api/health` | Health route exists; not proof of database/model/Neo4j readiness. |
| `GET, POST /api/projects`; `GET, DELETE /api/projects/<project_id>` | Org-scoped project CRUD. Creation forces embedding metadata; deletion only calls SQL repository. |
| `GET, POST /api/credentials` | Encrypted credential storage with safe output; query route does not resolve project's selected credential. |
| `GET, POST /api/data-sources` | Stores source configuration. Creating a `turso_ocr` source with a project starts a daemon thread immediately; no explicit dry-run/resume/retry endpoint. |
| `POST /api/projects/<project_id>/documents/upload` | Multipart `file` (multiple supported), or JSON filename placeholder. Processing is synchronous; returns 201 or 207 with per-file errors. `MAX_UPLOAD_MB` checks aggregate Content-Length, not a full per-file streaming limit. |
| `GET /api/projects/<project_id>/documents`; `DELETE .../documents/<document_id>` | List/status and SQL delete; no caller-side removal of Neo4j records or uploaded files. |
| `POST /api/projects/<project_id>/conversations` | Creates conversation metadata only. Query accepts `conversation_id` without scoped validation and does not persist chat messages/use history. |
| `POST /api/projects/<project_id>/query` | `{message, mode?, conversation_id?}` → `{answer, project_id, query_run_id, mode, sources[]}`. Mode is not validated/dispatched. Missing vectors returns HTTP 200 and a completed run with “no vector embeddings yet”; caught model/retrieval errors return 503 “Vector retrieval failed”. |
| `GET /api/projects/<project_id>/graph/status` | Calls `ensure_constraints` and `ensure_project` even on GET; returns external store status, not verified index readiness. |
| `GET /api/projects/<project_id>/graph`; `GET .../graph/data` | HTML visualization / graph JSON, also performing ensure calls; no semantic traversal in the answer path. |

Frontend upload proxy: `web/app/api/projects/[projectId]/documents/upload/route.ts`. Graph proxies: `web/app/dashboard/graph/[projectId]/{data,html}/route.ts`. Query is invoked via a server action, not a browser query API route.

### 2.3 Confirmed implementation defects and consequences

| Priority | Evidence | Required correction |
|---|---|---|
| P0 | `routes/query.py:27–52`: every mode follows identical vector-only code | Implement independent Neo4j vector, graph and hybrid retrieval; reject unsupported modes. |
| P0 | `services/vector_store.py:19–39,62–89`: all persisted/searched vectors are Turso-side | Migrate real vectors/text/provenance into Neo4j and switch both ingest and query paths after validation. |
| P0 | `ingestion_service.py:287–350`: skips extraction timeout/HTTP/parse errors; fallback entity/relation helpers; then sets ready | Preserve extraction method/failure counts and evidence, prohibit unsupported legal relations, distinguish partial/failed/chunk-only from GraphRAG-ready. External fallback helper behavior itself was not inspected. |
| P0 | OCR ingest creates random new document per row; cursor advances even on failure (`456–495`) | Stable source identity, durable retry ledger, content/version change detection; do not skip failed rows permanently or duplicate on reset/crash. |
| P0 | Graph is extracted from cleaned/rechunked text and then aggregated separately (`103–117,335–350`) | Map every extraction back to canonical chunks/spans; no untraceable assertions. |
| P0 | `web/lib/backend-actions.ts:82–93` discards query response; playground lines 118–143 show static conversation, lines 163–165 static performance | Render actual answer/evidence/errors and measured diagnostics; allow selecting intended corpus/mode. |
| P0 | `document-client.tsx:305` always displays Ready; chunk-only ingest also sets `ready` | Derive independent text/vector/graph readiness from backend coverage and index state. |
| P1 | `connection.py:35–39`, `project_service.py:35–38`, UI offers MiniLM/Nomic/Gemma | Stop rewriting metadata as a substitute for re-embedding; advertise only supported effective model/provider and record them per index generation. |
| P1 | `vector_store.upsert` only checks list counts; backfill skips any existing ID | Validate finite values/dimensions/model/content hash; repair stale vectors and remove stale chunk generations safely. Provider internals remain unverified. |
| P1 | SQL document/project delete does not call graph/files cleanup | Idempotent scoped cleanup/reconciliation across stores, including retention and shared-entity rules. |
| P1 | `auth_context.py:20`: shared-secret check only if configured; arbitrary identity headers otherwise; role is not enforced | Require trusted server context, enforce scoped permissions and validate conversation/source membership. |
| P1 | `graph-client.tsx:54–61` revisits nodes whenever level increases | Directed cycles/self-loops can grow the queue indefinitely. Use cycle-safe bounded layout and test cyclic legal graphs. |
| P1 | `web/lib/backend.ts` graph types expose only ID/label and endpoints; colors use array index | Add node/edge types, evidence and readiness; source navigation cannot be built from labels alone. |
| P1 | Source ingest uses daemon `Thread`; upload blocks request; cursor JSON updated separately from indexing | Backend-owned restart-safe batch worker/CLI with checkpoints, leases and reconciliation. No unrelated service dependency required. |
| P1 | `llm_client.py:142–147`: catches all errors into Ollama fallback with no explicit generation timeout; selected credential helper unused by query | Bound timeout/retries/context budget, report actual provider/fallback, wire credentials only when supported. |

### 2.4 Baseline verification and limits

| Check | Result |
|---|---|
| `git status --short`, `git diff --stat`, scoped Git diff | Initially only `?? IMPLEMENTATION_SPEC_CHECKLIST.md`; tracked source clean. |
| `bun run lint` in `web/` | **PASS**. |
| `bunx --no-install tsc --noEmit --incremental false` in `web/` | **PASS**, no diagnostics. |
| `bun run build` in `web/` | **PASS**, Next 16.3.3 production compilation/type checking/page generation completed. Does not verify authenticated runtime APIs. |
| Initial parallel frontend checks | Each exceeded 120 seconds; sequential retries with a 240-second limit passed. Preserve this history rather than describing timeouts as code failures. |
| `.venv/bin/python -m pytest backend -q -o addopts='' -p no:cacheprovider` from root | **NO TESTS COLLECTED**, `no tests ran in 0.07s`; not a passing backend suite. |
| Local SQLite schema/count inspection | Read-only snapshot results in Section 2.1; no data changed. |
| Flask startup, remote Turso/source schema, Neo4j, Ollama, live embeddings/retrieval and browser/citations | **NOT RUN / UNVERIFIED**. No production indexing or remote schema mutation performed. No scoped read-only diagnostic command currently exists; startup/backfill are mutating paths. |

### 2.5 Staged implementation plan (future work, in dependency order)

Each stage occupies its own run and ends with evidence, relevant tests/checks, Git-diff inspection and a report in this file. Stop after the stage; passing its exit criteria permits a later run, not automatic continuation. Failed or unverified criteria keep the current stage open. Proposed module/command/schema names are design proposals until implemented, not existing interfaces.

| Stage | Backend/frontend work | Exit evidence |
|---|---|---|
| A — Read-only live inventory | First build a standalone backend-owned diagnostic path with no app-factory/startup, migration, ensure/create, ingestion or backfill calls. Use read-only database connections/permissions and test its no-write behavior. Inventory source/application Turso and Neo4j; record eligibility and review in Section 2.7. Limit ownership changes to what this diagnostic needs. | Actual scoped counts, measured dimensions/model provenance, Neo4j node/edge/index/provenance coverage, and safely reusable vs re-embed/repair/unknown records recorded. Diagnostic tests prove no writes. Inventory reviewed; incomplete/unknown required measurements block exit. |
| B — Backend ownership, identity and state | After reviewed Stage A, implement backend-owned RAG interfaces and replace scoped `ai.*` runtime imports. Add necessary repeatable metadata migrations, stable org/project/source-record identity, canonical versioned chunks, retained source metadata, indexing ledger/retry state and formal readiness outputs (Section 5.3). | No LightRAG or sibling-service runtime dependency; same source twice produces one document/generation; failed rows retry; source spans survive extraction; state-transition tests pass; dry-run makes no writes. Any migration failure blocks exit. |
| C — Neo4j vectors + semantic retrieval | Validate served model dimensions, implement Neo4j chunk vectors/index and backend semantic search, then batch-copy only eligible Turso vectors or re-embed from canonical text. Preserve valid IDs and generation metadata; validate rollback before cutover. | Real vectors in Neo4j, index online, verified per-project coverage/integrity and query dimensions; reviewed paraphrase retrieval succeeds before generation. Record vector-mode results in Section 9.1; no fabricated vectors or unknown-provenance reuse. |
| D — Grounded graph + graph retrieval | Independently extract/resolve typed entities and source-backed relations from canonical chunk references; implement bounded semantic-seeded graph retrieval, idempotent merge and explicit partial failures. | Each assertion links to source chunk/span; extraction failures are visible; unsupported legal assertions rejected; graph-mode retrieval returns manually reviewed connected evidence (Section 9.1). |
| E — Retrieval + grounded API | Dispatch real vector/graph/hybrid modes; query embeddings → Neo4j candidates → bounded graph expansion → source-aware fusion → evidence budget → grounded generation. Add passage/citation and diagnostics contracts. | Independently tested modes; paraphrase + relationship queries retrieve reviewed real evidence; unanswerable/error paths do not fabricate answers. |
| F — Real frontend integration | Fix `web/lib/backend.ts` types/actions and playground results/corpus/mode selection; display formal backend readiness/errors and clickable source evidence. Graph-view/layout changes only if they block this flow. | Query displays actual answer/sources and mode, citations open authorized passages, partial/error/missing-vector states visible; lint/typecheck/build and core browser flow pass. |
| G — Core acceptance + indexing reliability | Complete backend-owned resumable indexing/retry/re-embedding, core integrity regressions, reviewed corpus evaluation, migration/restore/runbook and dependency-boundary checks. Broader operational/deletion features remain deferred unless blocking core integrity. | Relevant tests and real-service checks pass; independent vector/graph/hybrid evidence and citation reviews meet Section 9.1; indexing retry/idempotency and rollback recorded; applicable Section 12 gates satisfied. |

**Stage handoff record (complete after every stage):** stage ID and scope; sections completed and their Conventional Commit hashes (or verified no-change outcomes); exit criterion → evidence/result; commands and outcomes; changed/new files and Git-diff review; inventory/migration/readiness changes; blockers/deferred findings; next-stage eligibility. Each section follows implement → verify → update checklist → review diff → commit → next eligible section. No stage is currently implemented by this planning revision.

### 2.6 Neo4j target contract (proposed; not the current verified schema)

- **Ownership:** Turso holds application/control state; Neo4j holds retrieval chunks with real vectors plus typed evidence graph. The external OCR source remains read-only input. No steady-state dependence on Turso `chunk_embeddings` for retrieval after cutover.
- **Proposed topology:** tenant/project-scoped Document → Chunk containment; Chunk → Entity mentions; normalized typed entities and evidence-backed assertions. Store legal relationships only when supported; assertion records may carry relation type, endpoints and multiple evidence references rather than losing provenance on a merged edge. Actual current Neo4j labels must be inventoried before changing them.
- **Proposed chunk fields:** stable scoped identity, source document ID, chunk position, source content/hash, chunker/extractor version, available page/paragraph/span metadata, vector, effective provider/model/revision, measured dimension, index generation and timestamps. Use constraints compatible with the deployed Neo4j version. Proposed fields are not claims that existing nodes contain them.
- **Embedding baseline:** preserve the current Ollama EmbeddingGemma direction initially, subject to measured output compatibility. The declared Turso width is 768; do not assume every configured Ollama tag returns that width. Resolve the model once per generation, validate ingestion/query dimensions and numeric finiteness, prohibit mixing incompatible generations.
- **Vector index:** explicitly configure dimensions and cosine similarity on canonical chunk vectors. Discover Neo4j server version/edition and supported index/query syntax before implementing; do not infer capabilities from the `neo4j>=5.25.0` client dependency. Verify index ONLINE state and query plans.
- **Isolation:** filter org/project and model generation before candidate selection where supported; otherwise implement and test a partitioned/overfetch strategy for the deployed version. Post-filtering a global top-k alone can lose all relevant tenant results. Recheck scope on graph endpoints, traversal and source resolution; never send foreign evidence to the LLM.
- **Retrieval:** vector mode uses chunk similarity only; graph mode starts with semantic seeds and follows bounded allowed evidence-backed relationships; hybrid fuses semantic passages and graph evidence using a documented strategy (for example rank fusion, not addition of incomparable scores). Cap seeds, hops, fanout, total evidence and token budget. Record how graph evidence changes the final context.
- **LightRAG-inspired local/global retrieval:** local means query-relevant entities with nearby source evidence; broader retrieval means relationship-level evidence connecting themes/documents. Optional entity/relation description embeddings require their own measured/model-versioned index and provenance. Community summaries and embeddings are deferred, not mandatory P0 checkboxes.
- **Cross-store consistency:** SQL and Neo4j do not share a transaction. Use generation-aware staged writes, durable checkpoints and reconciliation; publish readiness only after vector + required graph stages succeed. Readers must not mix partial/new and old generations.
- **Migration:** inventory and backup first; decode real Turso vectors using supported read APIs, validate model/content/dimension, quarantine unknown provenance rather than relabeling it, transfer batches with checkpoints, compare scoped counts/content hashes and retrieval samples, then switch ingestion/query configuration together. Retain old data/read path for rollback until acceptance; no immediate DROP/re-ingest. Re-embed only incompatible/missing/stale units from canonical text.

### 2.7 Mandatory read-only live inventory and review gate

**Stage A must produce this report before any live schema/data mutation or migration.** Do not run `create_app`, `backend.run`, startup migrations, graph `ensure_*`, source creation, ingestion or legacy backfill to obtain it. Read-only means no SQL/Cypher writes, index/constraint creation, status/cursor updates or persistent probe vectors. Tests must verify that the diagnostic path does not import/execute mutating startup hooks and attempts no write statements. Safe model probes may measure output dimensions without storing/indexing their results.

- [ ] Record report timestamp, authorized org/project/source scope, redacted connection identifiers, database/server versions and reproducible read-only commands/queries. Use stable snapshot/watermark information where possible; record concurrent-change caveats.
- [ ] Measure actual source-document/OCR counts, application-document counts, canonical chunk counts and embedding totals/valid/missing/stale/invalid counts, separated by store, scope and generation. Distinguish missing schema from an empty table/index; reconcile overlapping records rather than adding counts blindly.
- [ ] Measure stored vector dimensions/distribution and numeric validity; record model/provider/revision provenance and query-model compatibility. Probe the intended served model's dimensions without persistence. A schema declaration, project-level model label or sample alone does not prove all vectors compatible; report any sampling and remaining unknown coverage.
- [ ] Measure Neo4j node counts by label/type, edges by relationship type, chunk/entity vector coverage, vector-index configuration/state and source-provenance coverage with explicit numerator/denominator (including assertions linked to valid chunk/document evidence), plus dangling/duplicate records.
- [ ] Classify migration records/counts with stable identifiers or a reproducible selector: **safe to copy**, **requires re-embedding**, **requires text/provenance repair**, or **unknown/blocked**. State evidence for classification; vectors with unknown model/content provenance are not safe to copy. Record the non-destructive repair/re-embedding plan and exclusions.
- [ ] Record measured findings and report artifact location here (a secret-free local report may live under `backend/`); do not substitute the old local SQLite snapshot or UI defaults for live inventory.
- [ ] Record inventory review: reviewer, date, scope, discrepancies/exclusions and migration eligibility decision. Present the report to the user for review; no migration or subsequent mutating stage starts until that review is recorded. Material changes to corpus/model/schema invalidate affected eligibility and require refreshed inventory/review.

**Current result:** Stage A diagnostic access attempted on 2026-10-18; blocked at SQL read-only enforcement/confirmation before schema/row reads (`query_only_unavailable`, `ValueError`). Live counts, vector compatibility and provenance coverage remain unknown; **migration gate CLOSED**. If access is unavailable or required dimensions/counts remain unverified, finish only independent Stage A tooling/tests, report the blocker and stop.

#### Stage A execution record — 2026-10-18 (open)

**A.1 selected bounded subset:** standalone read-only inventory transport, legacy SQL measurements, source mapping verification, graph schema discovery and transient model probe (Sections 2.7 / 11.3, tooling only). Scope and acceptance were announced before implementation: no app/startup or write paths, missing schema and unknown provenance explicit, regression tests and usage documentation. This is an incremental Stage A deliverable, not completion of Section 2.7 or permission to begin Stage B.

- [x] Implement standalone `backend.scripts.inventory`, owned by `backend/inventory/`, without `backend.app`, `ai.*` or LightRAG imports. Native Turso `vector_extract` decoding, complete paged legacy vector scan, source-table mapping from the existing scoped data-source row, read-only graph discovery and optional non-persisted Ollama probe are implemented.
- [x] Enforce SQLite file `mode=ro`, require confirmed SQL `query_only`, reject write/script/extension calls at the query boundary, use Neo4j read transactions and redact driver messages/connections. Require deployment read-only credentials as documented; READ_ACCESS alone is not authorization.
- [x] A.1 verification: `.venv/bin/python -m pytest backend -q -o addopts='' -p no:cacheprovider` **29 passed**; targeted `.venv/bin/ruff check backend/inventory backend/scripts/inventory.py backend/tests/test_inventory.py` **PASS**; `git diff --check` **PASS**. Initial 25-test run passed; initial Ruff findings were fixed before the final checks. Startup isolation is tested with forbidden-import interception; actual local database hash/read-only rejection and read-transaction-only Neo4j mocks are tested. Live read-only permission enforcement is not claimed from mocks.
- [x] A.1 final staged diff (all seven new files plus checklist evidence) reviewed; Conventional Commit `bc78080` succeeded. No unrelated work or credentials staged.
- [ ] A.2 live measurements/review: discover authorized identities, run scoped measurements where available, record artifacts, discrepancies and blockers. Full graph semantic provenance/vector coverage remains a later bounded Stage A increment after discovery establishes the real schema. Unknown required measurements block the stage.

**Implemented interface:** `.venv/bin/python -m backend.scripts.inventory --help`. Exact commands, configuration, read-only protections, classification rules and limitations: `backend/inventory/README.md`. New report paths are required; exit 2 intentionally keeps the migration/review gate closed. No runtime ingestion/query behavior or existing data is changed by this subset.

**A.2 selected bounded subset (before further editing):** execute identity discovery using the explicit existing `backend/.env`, improve secret-free access-failure reasons when discovery failed with an opaque `ValueError`, and record evidence/blockers. Acceptance: preserve read-only behavior and previous reports; expose only enumerated failure reasons; test config failures; no invented scope or counts; report every Stage A exit criterion and stop if required access remains blocked.

- [x] A.2 tooling/evidence subset verified: enumerated access reasons added; same scoped pytest command **32 passed**, targeted Ruff **PASS**, `git diff --check` **PASS**. Previous evidence was preserved; the retry used a new filename. Deployment read-only confirmation still failed; no schema/row read, source decrypt/connect, Neo4j query, model probe, startup, migration or indexing was executed by the discovery command.
- [x] Record attempted live command and secret-free artifact: `.venv/bin/python -m backend.scripts.inventory --env-file backend/.env --discover-scopes --output /tmp/opencode/inventory-scopes-20261018-retry.json`; report timestamp **2026-10-18T08:38:56Z**, connection fingerprint `sha256:6e5eb4f1f01a90d8`; versioned artifact `backend/inventory/reports/2026-10-18-access-blocker.json`. Initial attempt `/tmp/opencode/inventory-scopes-20261018.json` recorded an opaque `ValueError`; retry identified `query_only_unavailable`. Exit 2 is the command's documented closed-gate result, not a completed inventory. Neither attempt measures an empty corpus or proves credential validity.

**Stage A exit-gate handoff (blocked; stop this run):**

| Exit criterion | Evidence / result |
|---|---|
| Actual source/application scoped document, chunk and vector counts | **BLOCKED**: identity discovery stopped before schema/row reads; org/project/source identities not established. No counts invented and no local snapshot substituted. |
| Measured stored/served dimensions, model provenance and compatibility | **UNVERIFIED**: stored vectors/model not reached; no scope invented to run a probe. Probe tooling tested only. |
| Neo4j node/edge/index/vector/provenance coverage and integrity | **UNVERIFIED**: no authorized project identity established; deployed graph scope/topology still needs discovery and a bounded follow-up diagnostic increment. |
| Migration eligibility and non-destructive disposition | **CLOSED**: no live records classified; conservative tooling never authorizes legacy provenance-unknown vectors for copying. Preserve all existing data; recover source/content/model evidence before transfer/re-embedding. |
| Diagnostic tests prove no writes/startup | **PASS (tooling)**: 32 tests, including actual read-only SQLite rejection/hash preservation, forbidden startup imports, full pagination, remote read-only refusal, and Neo4j read-transaction mocks. Live permissions not certified. |
| Inventory reviewed with reviewer/date/scope/decision | **PENDING USER REVIEW**: this is an access-failure artifact, not a complete inventory eligible for approval. No migration or Stage B permitted. |

**Changed/new files and review:** A.1 committed `backend/inventory/{__init__.py,sql.py,report.py,graph.py,README.md}`, `backend/scripts/inventory.py`, `backend/tests/test_inventory.py`, and this checklist in `bc78080`. A.2 adds secret-free access reasons/tests, README evidence and `backend/inventory/reports/2026-10-18-access-blocker.json`; final status/diff/new artifact must be reviewed before its Conventional Commit. No application schema/data/readiness or frontend changes. Frontend checks were not rerun because this increment is standalone backend diagnostics.

**Required next action:** establish a verified read-only SQL access path supported by the deployed driver/server (current failure does not distinguish unsupported pragma from remote access failure), then rerun discovery and supply/confirm authorized org/project/source IDs. Obtain read-only Neo4j access and intended Ollama model access, complete graph/provenance diagnostics and live reconciliation, present the completed inventory for user review and record that review. Continue **Stage A only** in a subsequent run; Stage B is ineligible. Exact environment names and application launch commands remain in Section 11 and `backend/inventory/README.md`. Existing backend launch still performs schema writes and must not be used to resolve this diagnostic blocker.

---

## 3. Data and Schema Integrity

- [x] Inspect declared application schema/migration code and local snapshot before planning changes; evidence in Section 2.1.
- [ ] Verify live application/source Turso schemas and Neo4j constraints/indexes using read-only diagnostics before migration.
- [ ] Identify canonical document records and their stable IDs.
- [ ] Identify OCR text fields and preserve original text; do not treat OCR text as if it were the original PDF.
- [ ] Preserve available source metadata: case title, citation/case number, judgment date, court/bench/judges, source URI or S3 key, page number, section/paragraph number, and other existing fields. Only use fields that exist or can be reliably extracted.
- [ ] Define or verify a stable chunk identity, preferably derived from document ID plus chunking version and chunk position/content hash.
- [ ] Define Neo4j schema for canonical chunks, vectors, entities, assertions and evidence; keep application identities/index-job state in Turso. Reuse verified current records through a safe migration.
- [ ] Persist unique org/project/source/source-record mapping and content fingerprint; do not create new UUID documents on every OCR-source replay.
- [ ] Replace source cursor-only progress with per-document stage/generation/retry state; retry failures even after the forward cursor advances.
- [ ] Preserve source URI and legal metadata instead of overloading filename; explicitly handle the currently unused `url_column` and flattened PDF page text.
- [ ] Store model name/version, vector dimension, chunking version, and indexing timestamp with embedding/index metadata where feasible.
- [ ] Ensure each derived chunk/entity/relationship can be traced to one or more source documents and source chunks.
- [ ] Add migrations only when necessary and make them safe and repeatable.
- [ ] Add integrity checks for orphan chunks, orphan embeddings, dangling edges, duplicate IDs, and missing source provenance.
- [ ] Make document/project deletion reconcile Turso, Neo4j and retained uploads; preserve shared entities only while valid in-scope evidence remains.
- [ ] Remove unconditional startup embedding-metadata rewrites; metadata changes must correspond to measured compatible vectors or an explicit re-embedding migration.
- [ ] Document how to back up and restore the relevant data before any destructive operation.

**Acceptance criteria**
- The system can report document, chunk, embedding, entity, and relationship counts from actual data.
- Every indexed chunk resolves to its source document.
- No destructive schema or data changes are made without a documented migration/rollback path.

---

## 4. OCR Text → Chunks → Embeddings Pipeline

- [ ] Reuse existing OCR text from the verified data source; do not re-run OCR unless the existing content is missing or demonstrably unusable.
- [ ] Normalize text conservatively while preserving paragraph, page, heading, and citation boundaries when available.
- [ ] Implement or verify chunking suitable for long legal judgments. Avoid splitting citations, paragraph labels, and sentences unnecessarily.
- [ ] Keep document ID, chunk ID, chunk position, page/paragraph metadata, and source text with every chunk.
- [ ] Select an actual embedding model supported by the project configuration. Document its name, output dimensions, and provider.
- [ ] Generate embeddings from the **actual chunk text**. Do not embed only document titles or graph labels when chunk-level semantic retrieval is required.
- [ ] Validate each embedding: expected dimension, finite numeric values, non-empty source text, and model/version consistency.
- [ ] Persist real numeric chunk vectors and model/generation metadata on Neo4j retrieval nodes; create and verify a dimension-compatible cosine vector index.
- [ ] Implement query-vector search using supported Neo4j vector-search capabilities with org/project/generation isolation and a documented candidate-selection strategy (Section 2.6).
- [ ] Migrate compatible existing Turso `F32_BLOB(768)` vectors with verified decoding and counts; retain legacy data until retrieval comparison and rollback pass. The existing libSQL vector implementation is real code, but is not the requested final store.
- [ ] Make indexing idempotent: rerunning it must update missing/stale records without duplicating chunks, embeddings, nodes, or edges.
- [ ] Support resumable/batched processing and useful progress logs for a large corpus.
- [ ] Record failures per document/chunk and allow safe retries.
- [ ] Add an explicit re-embedding path when the embedding model, dimensions, or chunking version changes.
- [ ] Skip a previously embedded chunk only when identity, text hash, model revision, dimensions and generation match; the current backfill's existence-only skip is insufficient.
- [ ] Add a dry-run/diagnostic mode that reports work to be done without mutating data.

**Acceptance criteria**
- A sample of stored vectors is demonstrably generated from chunk text by the configured model.
- Stored dimensions and model metadata match the configured model.
- A semantic query retrieves relevant chunks that are not exact keyword matches.
- Re-running indexing does not increase counts for already indexed, unchanged records.
- Missing or malformed embeddings are reported and can be repaired.
- Neo4j holds and searches the vectors; a declaration of a vector index or embeddings left only in Turso is insufficient.

---

## 5. Knowledge Graph / GraphRAG — Critical Requirements

### 5.1 Graph design and provenance

- [x] Identify scoped Neo4j integration points/configuration; actual external-store schema remains unverified (Section 2).
- [ ] Inventory deployed Neo4j labels/relationships/properties/constraints/indexes and implement the backend-owned store; keep outside-scope store internals unassumed.
- [ ] Define meaningful node types based on the corpus, for example: `Document/Judgment`, `Chunk/Paragraph`, `Person/Judge`, `Court/Bench`, `LegalConcept`, `Statute/Section`, `Case/Citation`, and `Organization`. Use only types that can be extracted reliably.
- [ ] Define typed, meaningful edges, for example: `CONTAINS`, `CITES`, `CITED_BY`, `DECIDED_BY`, `MENTIONS`, `INTERPRETS`, `OVERRULES`, `DISTINGUISHES`, or `RELATED_TO`. Do not create legal relationship edges unless evidence supports them.
- [ ] Attach provenance to extracted entities and relationships: source document ID and source chunk/paragraph, plus extraction confidence or method where available.
- [ ] Extract against canonical source-chunk references; preserve evidence spans through OCR cleanup/rechunking and retain all supported evidence when deduplicating entities/relations.
- [ ] Record extraction timeout/parse/error and fallback method separately; synthetic/co-occurrence relationships must never be presented as proven legal relationships.
- [ ] Deduplicate entities using a documented normalization/resolution strategy. Do not merge distinct people, cases, or statutes based only on similar names.
- [ ] Ensure graph edges have valid endpoints and source evidence.
- [ ] Preserve source metadata and support navigation from a graph result to the underlying judgment and text passage.

### 5.2 Embeddings are required — no graph-only implementation

- [ ] Generate and persist embeddings for **document chunks in Neo4j** using the effective, versioned embedding model.
- [ ] If the chosen GraphRAG design uses entity, relation, or community embeddings, generate and persist those too; document exactly which graph elements have embeddings and why.
- [ ] Link every embedded chunk to its graph representation and source document where applicable.
- [ ] Implement a query-embedding path using the same compatible model/version as the indexed vectors.
- [ ] Implement semantic candidate retrieval over embedded chunks and/or graph elements before graph expansion or graph traversal.
- [ ] Implement graph retrieval that uses query-relevant seeds, then traverses meaningful relationships under defined depth/size limits.
- [ ] Implement a hybrid retrieval path that can combine vector candidates and graph-derived evidence, with deduplication and source-aware ranking.
- [ ] Ensure the graph is not populated exclusively with generic content nodes; it must include typed entities and meaningful, evidence-backed relationships where extraction supports them.
- [ ] If entity extraction or graph construction fails, surface an error/status. Do not silently return a graph that looks successful but has no usable semantic index.
- [ ] Implement the formal states and separate capabilities in Section 5.3. `skip_graph_extraction` cannot produce `graphrag_ready` status.
- [ ] Add a diagnostic command/report showing node types, edge types, embedding coverage, provenance coverage, and dangling records.
- [ ] Add tests proving that graph retrieval returns evidence relevant to a query and that results link back to source chunks.

**Graph acceptance criteria**
- The graph contains typed nodes and meaningful typed relationships, not just a visual collection of content nodes.
- Every returned graph result is traceable to source evidence.
- The system can report embedding coverage separately for chunks, entities, and communities, as applicable.
- A query can use embeddings to identify relevant seed content and graph relationships to expand or connect evidence.
- Graph-only visualization does not count as completion of GraphRAG.
- If the implementation intentionally uses a named GraphRAG algorithm that embeds only certain levels (for example, community summaries rather than every entity), document that design and test its actual retrieval path. Do not add arbitrary embeddings merely to tick a box; implement the selected approach correctly.

### 5.3 Formal backend readiness contract (required; not currently implemented)

Expose readiness as validated backend output for each document/index generation and scoped corpus, not as a UI label or the ingestion function's return value. Include a `state`, separate text/vector/graph capability flags, current generation, measured coverage/integrity results, verification timestamp and structured failure reasons/retry eligibility. These are proposed contract fields to implement and test, not existing response properties.

| State | Required meaning / proof |
|---|---|
| `pending` / `processing` | Required work is absent/in progress; no implied readiness. |
| `text_ready` | Source text and canonical chunks exist with stable identity and valid source linkage; vector/graph readiness is not implied. |
| `vector_ready` | Required chunk embeddings for the advertised scope/generation are valid, model/dimensions compatible, Neo4j index online and semantic retrieval verified. Graph extraction may be unrequested/skipped; this never means GraphRAG-ready. |
| `graph_partial` | Some required graph extraction, relationship provenance or graph integrity work failed/is incomplete; expose the affected records and reasons. Valid vector capability may remain usable if explicitly reported. |
| `graphrag_ready` | Required embeddings/index, typed evidence-backed graph relationships, semantic-seeded graph and hybrid retrieval paths, source resolution and integrity checks all pass for the advertised scope/generation. Retrieval verification references the reviewed tests in Section 9.1. No unresolved required graph failures. |
| `failed` | A required processing stage failed and needs retry/intervention. Preserve successful capability flags/evidence and report the failed stage; do not report overall success. |

- [ ] Persist/publish evidence-driven transitions: `pending/processing` → `text_ready` → `vector_ready`; incomplete graph work → `graph_partial`, required-stage errors → `failed`, verified graph/retrieval/integrity completion → `graphrag_ready`. Retries re-enter processing; return alone never advances readiness.
- [ ] Do not expose an ambiguous bare `ready` value. Any legacy compatibility mapping must preserve precise state and cannot map chunk-only/vector-only success to GraphRAG-ready.
- [ ] Report capabilities separately from the summary state so a partial graph cannot hide usable vector retrieval or falsely enable graph/hybrid modes. Reject unavailable modes with explicit diagnostics rather than silently falling back.
- [ ] Compute corpus readiness for an explicit advertised document set/generation; expose excluded/failed/pending counts. Do not mark a whole corpus GraphRAG-ready because one document is ready or silently exclude failed documents.
- [ ] Invalidate affected readiness on content/model/chunker changes, stale/missing vectors, index outage or failed integrity checks; only publish a new generation after its required checks pass.
- [ ] Test transitions for chunk-only ingestion, malformed vectors, provider/extraction/provenance failure, interrupted indexing, retry and generation change; verify Flask outputs and frontend badges use this contract.

---

## 6. Retrieval and Answer Generation

- [x] Trace current question/project/org query contract in source; live behavior remains unverified (Section 2.2).
- [ ] Implement real mode validation/dispatch; do not echo `hybrid` while doing vector-only retrieval.
- [ ] Implement semantic chunk retrieval using compatible query embeddings and Neo4j chunk-vector indexes.
- [ ] Implement or verify graph retrieval using semantic seeds, typed relationships, and source provenance.
- [ ] Add hybrid retrieval when both vector and graph results are available.
- [ ] Deduplicate retrieved passages and preserve ranking scores and source metadata.
- [ ] Add optional reranking only if configured and tested; do not represent a no-op as reranking.
- [ ] Pass retrieved evidence to the configured LLM with explicit instructions to answer from evidence and acknowledge insufficient evidence.
- [ ] Return source citations in a structured format, including document identity and page/paragraph references where available.
- [ ] Extend response with stable citation IDs, source excerpt/span, available legal metadata, retrieval method/path and measured scores; distinguish citation candidates from citations actually used in the answer.
- [ ] Provide an authorized source-passage resolution route/viewer (new contract to define), so citations can open real text even when a source PDF URL is unavailable. Do not fabricate page numbers for flattened OCR.
- [ ] Ensure the answer API distinguishes answer text, citations, retrieval diagnostics, and errors.
- [ ] Return an explicit no-index/partial-index/insufficient-evidence status rather than recording missing vectors as a successful completed answer.
- [ ] Enforce a bounded evidence/context token budget and meaningful score/coverage handling before generation.
- [ ] Do not fabricate case names, quotations, paragraph numbers, citations, or holdings.
- [ ] Add timeout, retry, and error handling for model and database calls.
- [ ] Report actual provider/model/fallback for the core query path; selected-credential/BYOK wiring is deferred unless it blocks the configured working provider. Do not advertise unsupported selection behavior.
- [ ] Validate `conversation_id` belongs to the authorized project/org/user before use; conversation memory remains P2 until message persistence/history retrieval are implemented.
- [ ] Test questions requiring exact text, semantic paraphrase, case citation lookup, and multi-document/relationship reasoning.

**Acceptance criteria**
- A query produces retrieved passages before answer generation; logs or test instrumentation can demonstrate this.
- Every citation maps to a real source record and relevant passage.
- An unanswerable query does not receive a confident, unsupported legal answer.
- Vector and graph retrieval can be run and evaluated independently.

---

## 7. Flask Backend

- [x] Document current route names, observed contracts and error gaps (Section 2.2).
- [ ] Keep configuration and secrets in environment variables; provide an `.env.example` with placeholders only.
- [ ] Validate request payloads and return consistent HTTP status codes.
- [ ] Add endpoints or commands for indexing status and diagnostics if missing.
- [ ] Make diagnostics/status read-only; current graph GETs must not create constraints/projects. Decouple schema migration from app factory startup.
- [ ] Ensure long indexing tasks do not block ordinary query requests indefinitely; use the project's existing background-job approach or document a safe batch command.
- [ ] Add structured logs for indexing, embedding, retrieval, graph construction, and model calls. Do not log API keys or sensitive document content unnecessarily.
- [ ] Enforce project/document access boundaries wherever multi-tenancy exists.
- [ ] Require a configured internal secret/trusted server boundary; validate roles and conversation/source membership rather than accepting spoofable identity headers when secret is empty.
- [ ] Add tests for successful requests, invalid input, missing configuration, database errors, and model-provider errors.
- [ ] Verify CORS and frontend API configuration for development and production.

---

## 8. Next.js Frontend

- [x] Audit document, graph, playground pages/components, API types/actions, auth and backend forwarding before planning changes (Section 2).
- [ ] Verify the UI calls the real Flask endpoints rather than using mock data or hard-coded examples.
- [ ] Show clear loading, empty, partial, success, and failure states for document indexing and queries.
- [ ] Show ingestion/indexing status based on backend data, not optimistic assumptions.
- [ ] Display answers with clickable, source-grounded citations.
- [ ] Return query results from the action/API and render them in playground state; remove static conversation/reasoning/performance as substitutes for real output.
- [ ] Select the actual corpus and retrieval mode rather than always submitting `projects[0]` with hidden `hybrid`.
- [ ] Align model choices with the effective backend model; no MiniLM/Nomic selection while silently generating Ollama Gemma vectors.
- [ ] If graph visualization exists, distinguish node types and edge types and expose source evidence when a node/edge is selected.
- [ ] Fix directed-cycle/self-loop layout termination in `graph-client.tsx:54–61`; graph data must have traversal/size limits and provenance-rich types.
- [ ] Make it clear when a graph is not yet indexed or embeddings are missing; do not show a misleading “ready” state.
- [ ] Handle API timeouts, backend unavailability, and malformed responses without crashing the page.
- [ ] Verify responsive layout and accessibility of important controls.
- [x] Baseline lint, TypeScript checks and production build pass on 2026-10-18 (Section 2.4).
- [ ] Re-run frontend checks after implementation and verify authenticated query/indexing/citation flows in a browser.

---

## 9. Evaluation and Regression Tests

- [ ] Create a small, repeatable test set from the available Supreme Court corpus with expected relevant source passages. Do not fabricate expected answers.
- [ ] Include exact-match queries, paraphrased semantic queries, citation/case-name queries, and relationship/multi-hop queries.
- [ ] Test at least one query where keyword search alone is insufficient.
- [ ] Test vector retrieval separately from graph retrieval and hybrid retrieval.
- [ ] Measure retrieval quality using appropriate metrics where labels exist (for example, Recall@k, Precision@k, or MRR); otherwise report manual evaluation honestly.
- [ ] Measure answer faithfulness/citation validity on a small reviewed sample.
- [ ] Add regression tests for empty corpus, missing embeddings, malformed vectors, graph nodes without provenance, duplicate indexing, and provider failures.
- [ ] Place backend tests under `backend/tests/` and frontend tests under `web/`; baseline scoped backend suite currently collects zero tests. Do not rely on unrelated root service tests for completion.
- [ ] Add a dependency-boundary check over first-party backend/web source and manifests: no LightRAG dependency/calls and no sibling `ai.*` runtime imports. Textual reference in this plan is not a dependency.
- [ ] Test tenant-isolated top-k (including a corpus dominated by another tenant), graph cycles/fanout, stale model generations, interrupted cross-store writes, deletion cleanup and failed-source retry after cursor advance.
- [ ] Record latency and cost where available; do not optimize by removing required functionality without documenting the trade-off.

### 9.1 Required manually reviewed Supreme Court retrieval set

**Completion requires at least one small, manually reviewed, repeatable test set drawn from actual available Supreme Court judgments.** Create the set once source access is available, before retrieval acceptance/cutover; freeze source/chunk identities, content hashes and index/model generation. Human review must verify expected passages against original OCR/source text, not infer relevance from the generated answer. Missing access or missing review blocks retrieval acceptance, not permission to invent fixtures.

- [ ] Include exact passage/case-citation lookup, semantic paraphrase that keyword-only retrieval misses, and a relationship/multi-document query with all required supporting passages. Include an unanswerable control.
- [ ] Record each query and expected source document/chunk IDs, passage text or reproducible span, available page/paragraph references, and why that evidence is relevant; record reviewer/date. Define expected graph connections for relationship cases without inventing legal assertions.
- [ ] Run the same set independently in **vector**, **graph** and **hybrid** modes. Capture actual execution-path diagnostics, retrieved ranked passages (including IDs/text/spans), scores/path evidence, and correctness separately for every query/mode. A mode-irrelevant case may have a documented expected limitation, never a fabricated pass.
- [ ] Set and record top-k/evidence budgets and per-case pass criteria before evaluation. Required semantic paraphrase must retrieve its expected passage; required relationship cases must recover all necessary linked evidence in graph/hybrid, with provenance. Report misses, Recall@k/MRR where labels permit and manually reviewed correctness; do not hide failing required cases behind average scores.
- [ ] Verify graph traversal actually contributes relevant connected source evidence beyond its semantic seeds; an identical vector-only path with a different mode label fails graph acceptance.
- [ ] Review every returned citation in this small set for correct document/passage resolution and support for the cited claim; unanswerable cases must expose insufficient evidence without confident invented legal claims.
- [ ] Record/review failures, fix required cases and rerun affected modes before declaring completion. Passing unit tests, convincing answer prose or a populated graph is not retrieval-quality evidence.

**Result record template — one row per query and retrieval mode** (detailed passage output may be stored in a secret-free versioned fixture/report under `backend/`):

| Test / query | Expected source passages and graph connection, if applicable | Actual ranked retrieved passages / evidence artifact | Mode and executed path | Correct? / failure reason | Reviewer / date / corpus-model-generation / k |
|---|---|---|---|---|---|
| Pending — populate from real corpus | Not yet reviewed | Not run | Run vector, graph and hybrid separately | Unverified | Pending |

Record retrieval correctness separately from answer faithfulness. An eloquent answer cannot compensate for missing expected evidence, an unexecuted graph path or invalid citations.

### Minimum regression scenarios

| Scenario | Expected result | Status |
|---|---|---|
| Index a new OCRed judgment | Chunks, embeddings, graph records, and provenance created as configured | Unverified |
| Re-run indexing unchanged | No duplicate records | Unverified |
| Query with semantic paraphrase | Relevant source chunks retrieved | Unverified |
| Query requiring case/entity relationships | Graph adds relevant connected evidence | Unverified |
| Query with missing embeddings | Clear diagnostic/error or repair path; no false success | Unverified |
| Citation click-through | Opens the correct judgment/passage | Unverified |
| Database/provider unavailable | Clear error; no fabricated answer | Unverified |
| Re-index after model/version change | Stale embeddings detected and safely regenerated | Unverified |
| Query modes | Vector, semantic-seeded graph, and fused hybrid execute distinct tested paths | Missing |
| Replay OCR source / retry failed row | Stable source identity; no duplicate documents; failures retried despite advanced cursor | Missing |
| Neo4j vector migration and rollback | Matching scoped vector/text coverage, valid model metadata and recoverable read cutover | Missing |
| Tenant-isolated vector top-k | No leaked evidence; authorized relevant hits survive competing-tenant candidates | Unverified |
| Cyclic/self-referential graph UI | Layout terminates with bounded work; evidence inspectable | Broken (static finding, Section 2.3) |
| Delete document/project | SQL, vector/graph evidence and retained files reconciled by policy | Partial |
| Dependency boundary | Backend/frontend work without LightRAG or sibling-service runtime imports | Missing (current `ai.*` imports) |

---

## 10. Security and Reliability

- [ ] Confirm credentials are not committed to source control or emitted in logs.
- [ ] Treat retrieved documents as untrusted data, not system instructions.
- [ ] Prevent prompt injection in document text from overriding system/developer instructions or granting unauthorized tool access.
- [ ] Scope retrieval by the current user's authorized project/tenant, where applicable.
- [ ] Validate external URLs and storage keys before fetching content.
- [ ] Limit graph traversal depth, candidate count, and query work to avoid runaway requests.
- [ ] Validate Neo4j scope and active model generation on every vector/graph/source lookup; test retrieval recall as well as non-leakage when tenant filters interact with ANN top-k.
- [ ] Add sensible request timeouts and resource limits.
- [ ] Document backup, recovery, and re-indexing procedures.
- [ ] Report known limitations; do not claim that guardrails eliminate all prompt-injection or hallucination risk.

---

## 11. Configuration and Runbook

- [x] Record discovered configuration names/purposes and gaps below; no secret values included.
- [x] Record existing frontend/backend launch commands below; production runtime integrations remain unverified.
- [ ] Document how to connect to Turso safely.
- [ ] Document the indexing/embedding command, dry-run mode, resume behavior, and expected output.
- [ ] Document how to inspect embedding and graph coverage.
- [ ] Document how to run tests, lint, typecheck, and production build.
- [ ] Document known external requirements (model credentials, S3 access, embedding provider, etc.).
- [ ] Verify the instructions work from a clean checkout as far as available credentials allow.

### 11.1 Discovered configuration (existing code, not a new config contract)

Configure `backend/.env` and `web/.env` separately. Never paste credentials into this checklist. Requirements below describe current consumers; future Neo4j-only retrieval still needs the application Turso database.

| Component / variable | Purpose and current requirement |
|---|---|
| Backend `TURSO_DATABASE_URL` (alias `TURSO_CONNECTION_URL`), `TURSO_AUTH_TOKEN` | Required by connection/startup; application metadata and currently vectors. Source OCR connection is separately configured per data source. |
| Backend + web `BACKEND_INTERNAL_SECRET` | Shared server-to-server trust secret; required by target design. Current backend permits missing-secret bypass; fix before claiming enforced auth. |
| Backend `CREDENTIAL_ENCRYPTION_KEY` | Required for storing/reading encrypted provider/source credentials; preserve across restarts and backup/restore. |
| Backend `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD` | Neo4j graph now, graph + vectors in target. Use deployment-specific credentials; replace insecure hard-coded password defaults/example. No configurable Neo4j database name found; add one only if implemented and documented. |
| Backend `OLLAMA_BASE_URL`, `OLLAMA_EMBEDDING_MODEL` | Embedding endpoint/model tag, default model `embeddinggemma`; required for current query/index path. Served model and measured dimensions must be verified. |
| Backend `EMBEDDING_BATCH_SIZE` | Optional batching, default 16. |
| Backend `GRAPH_LLM_MODEL`, `GRAPH_LLM_TIMEOUT_SECONDS`, `GRAPH_LLM_NUM_PREDICT`, `GRAPH_LLM_NUM_CTX` | Optional graph extraction settings; default model `smollm2:135m`, 60-second timeout, 700 predictions, 4096 context. Small default's legal extraction quality has not been evaluated. |
| Backend `GRAPH_EXTRACTION_MAX_CHUNKS`, `GRAPH_CHUNK_SIZE`, `GRAPH_CHUNK_OVERLAP` | Optional graph sampling/chunk controls; defaults 0 (all), 300, 30 in Config. Effective limits/coverage must be reported. |
| Backend `PLATFORM_LLM_BASE_URL`, `PLATFORM_LLM_API_KEY` (alias `GEMINI_API_KEY`), `PLATFORM_LLM_MODEL` | OpenAI-compatible answer provider. Default endpoint targets Gemini compatibility API, model `gemini-2.5-flash`; key needed for that provider. Current code falls back to Ollama on any exception. |
| Backend `FALLBACK_LLM_MODEL` | Ollama answer fallback, default `smollm2:135m`; currently no explicit timeout. |
| Backend `UPLOAD_DIR`, `TMP_DIR`, `MAX_UPLOAD_MB` | Optional local storage/resource settings; relative defaults require launching backend from repository root. Temp setting is declared; no verified full temp-file lifecycle. |
| Backend `UNSTRUCTURED_API_KEY`, `UNSTRUCTURED_API_URL` (legacy alias `UNSTRUCTURED_API_UR`), `UNSTRUCTURED_POLL_SECONDS`, `UNSTRUCTURED_PARTITION_STRATEGY` | Optional OCR fallback for uploads without embedded text; not required for existing OCR-source ingestion. Default polling 10 seconds, strategy `hi_res`. |
| Web `TURSO_CONNECTION_URL`, `TURSO_AUTH_TOKEN` | Required by `web/db/index.ts` for auth database. Do not assume web/application/source DBs are identical. |
| Web `BETTER_AUTH_SECRET`, `BETTER_AUTH_URL` | Auth signing/base URL; required for intended authenticated runtime. |
| Web `BACKEND_URL` | Backend server URL, defaults to `http://localhost:5000`; server-side only. |
| Web `RESEND_API_KEY` | Required for current magic-link sign-in and invitations. |
| Web `RESEND_FROM_EMAIL` | Present in example but unused: `lib/auth.ts` hard-codes sender instead. Correct the configuration contract. |
| Web `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Listed in example, but no corresponding social-provider setup found in `lib/auth.ts`; not verified working login options. |

**Example/config drift to fix:** backend example omits embedding settings, graph tuning and several platform LLM keys. It advertises `DEFAULT_UNSTRUCTURED_API_URL`, `DEFAULT_OCR_STRATEGY`, `MAX_OCR_BATCH_SIZE` and `FLASK_ENV`, which the audited `Config`/ingestion path does not consume as those settings. Replace with actual supported names; source batch size currently comes from source metadata. Document defaults once, with placeholders rather than working passwords. Keep runtime/version/model compatibility explicit.

### 11.2 Existing launch and check commands

Use a project Python environment with `backend/requirements.txt` dependencies installed. Existing code additionally imports sibling `ai.*`; until Stage A is complete it is not a self-contained backend install. Frontend dependencies are recorded in `web/bun.lock`.

```bash
# Repository root: backend (WARNING: current startup executes schema/migration writes)
.venv/bin/python -m backend.run

# In web/: frontend development, or production after build
bun run dev
bun run build
bun run start

# In web/: baseline checks
bun run lint
bunx --no-install tsc --noEmit --incremental false

# Repository root: scoped backend tests (currently collects zero tests)
.venv/bin/python -m pytest backend -q -o addopts='' -p no:cacheprovider
```

Current mutating legacy repair command, **not the target Neo4j migration/indexer**:

```bash
# Repository root; invokes create_app(), reads existing Neo4j chunks, writes Turso vectors.
# No dry-run flag; existence-only resume; not executed during this audit.
.venv/bin/python -m backend.scripts.backfill_embeddings \
  --project-id <project-id> --organization-id <organization-id> --batch-size 16
```

Existing OCR ingestion is triggered by `POST /api/data-sources` with `source_type='turso_ocr'`, project and source mapping/credentials, and immediately starts a daemon thread. Do not use source creation as a diagnostic or replay command. No verified general indexing/dry-run/retry CLI exists within scope.

### 11.3 Required operational interfaces (proposed, not implemented commands)

- Read-only scoped inventory: database/source schemas, document/chunk/vector counts, model/dimension distribution, index readiness, node/edge types, source evidence coverage and orphan/stale records. Must not call app initialization or ensure/migration functions.
- Explicit repeatable schema migration with backup/rollback, separate from request startup and GET status.
- Batch indexing/repair runner accepting org/project/source scope, dry-run, resume/retry-failed, batch limits, active generation and explicit re-embedding selection. Document exact syntax after implementation rather than inventing a working CLI here.
- Turso-vector → Neo4j-vector migration with dry-run, compatible-vector validation, checkpoint/resume, reconciliation report, read cutover and rollback.
- Per-stage readiness/health and core indexing reconciliation report; broader deletion repair is deferred unless needed for core integrity. No destructive operation as a default diagnostic.
- Backend tests, real-service smoke tests, evaluated retrieval queries and authenticated UI citation flow with reproducible expected evidence.

---

## 12. Completion Gate — Do Not Declare Done Until These Pass

These are core RAG acceptance gates, subject to Section 1 scope control. Retained deferred findings elsewhere are not additional unconditional completion gates. A stage report may declare that stage complete only; it must not declare the entire project complete.

- [x] Initial scoped static audit and available baseline evidence recorded in Section 2; live data audit remains a separate gate below.
- [ ] Every completed stage has its own run/handoff, relevant test results, inspected Git diff and passed exit criteria; no stage advanced across a failed/unknown gate.
- [ ] Each completed implementation section has a successful Conventional Commit containing its intended changes/checklist evidence before the next section began, or a documented verified no-change outcome; section scope and commit hashes are reported in the stage handoff.
- [ ] Backend-owned RAG path is independent of sibling services and has no LightRAG dependency/import/invocation.
- [ ] Section 2.7 live inventory, migration eligibility classifications and user review are recorded before any migration/mutating stage; no missing required counts or unverified dimensions.
- [ ] Existing OCR corpus is read from the verified source without unnecessary re-OCR.
- [ ] Chunks preserve source identity and available legal-document metadata.
- [ ] Real chunk embeddings have been generated/migrated into Neo4j, with dimension-compatible vector index ONLINE and isolated query retrieval verified.
- [ ] Embedding dimensions/model versions are validated.
- [ ] Semantic retrieval demonstrably uses query and corpus embeddings.
- [ ] Graph has meaningful typed entities and relationships with source provenance.
- [ ] Graph retrieval uses semantically relevant seeds and meaningful relationships.
- [ ] Vector, graph, and hybrid retrieval behavior is testable independently.
- [ ] Section 5.3 formal backend readiness states/capabilities are tested; `graphrag_ready` is derived from verified evidence/integrity/retrieval, never ingestion return alone.
- [ ] Section 9.1 real Supreme Court test set is manually reviewed, with expected/actual passages, independent mode execution and per-case correctness recorded; required retrieval and citation cases pass.
- [ ] Flask endpoints return grounded evidence and valid citations.
- [ ] Next.js UI uses real backend data and handles failure/loading states.
- [ ] Indexing is repeatable, idempotent, observable, and recoverable.
- [ ] Source replay, failed-row retry, generation changes and interrupted writes pass core reconciliation tests. Deletion tests are required here only if deletion was a documented blocker promoted into core scope.
- [ ] Turso-vector cutover comparison and rollback are documented and verified; no required retrieval depends on the legacy Turso vector table after cutover.
- [ ] Relevant backend tests pass.
- [ ] Frontend lint/typecheck/build pass.
- [ ] Core regression scenarios in Section 9 have recorded outcomes; deferred visualization/deletion/platform findings are explicitly identified rather than silently treated as passes.
- [ ] Runbook and configuration documentation are updated.
- [ ] Final summary lists completed work, unresolved items, evidence, and commands.

---

## 13. Current Audit/Planning Report — Implementation Still Pending

This report summarizes the documentation task completed on 2026-10-18. Replace/extend with measured implementation results after executing the plan; the unchecked implementation gates above are intentional.

### Completed
- Detailed scoped static audit of backend ingestion, configuration/schema, vector store, graph integration, generation, auth, routes and frontend API/actions/document/graph/playground flows.
- Recorded observed defects, actual vs assumed schema/model information, safe migration requirements, Neo4j graph + embedding target and seven ordered implementation stages.
- Explicit LightRAG conceptual-only restriction and backend/frontend ownership boundary.
- Frontend baseline lint/typecheck/build; local SQLite snapshot read-only inventory; scoped test collection result.
- Planning refinement: one-stage-per-run execution/handoff limit, reviewed read-only inventory gate, formal readiness outputs, actual-corpus manual retrieval evaluation and explicit deferral of non-blocking platform work. These requirements are specified, not implemented or verified.

### Partially completed / not completed
- No RAG application implementation performed by this checklist revision. Existing vector-only query path, graph fallbacks, misleading readiness and static playground still require the listed changes.
- Remote application/source Turso and Neo4j schema/counts, real embedding compatibility, extraction provenance, retrieval quality and browser citation behavior remain unverified.
- No scoped backend tests currently collected; sibling-service implementation/tests not audited.

### Important files changed
- `IMPLEMENTATION_SPEC_CHECKLIST.md` — audit, target architecture, stage plan, acceptance criteria and configuration/runbook.

### Data/schema changes
- None. Local snapshot inspected read-only; no remote startup/migration/indexing executed.

### Embedding implementation
- Model: current backend selects external Ollama `EmbeddingGemmaProvider` with configured tag (default `embeddinggemma`); project metadata hard-codes `google/embeddinggemma-300m` / `huggingface`. Effective live model unverified.
- Dimensions: current SQL declaration 768; actual generated/stored dimensions not measured.
- Storage format: current Turso `F32_BLOB(768)` via `vector32(JSON)`; required target Neo4j numeric vectors + versioned metadata/vector index.
- Retrieval strategy: current project-filtered SQL cosine-distance sort; required target isolated Neo4j vector search and graph/hybrid dispatch.
- Coverage measured: no live coverage measured; local snapshot lacks embedding table and has zero document rows.

### Graph implementation
- Storage/backend: current calls to external Neo4j store; target first-party backend Neo4j graph/vector implementation.
- Node types: live/current external schema unverified; proposed scoped Document/Chunk/typed Entity/assertion design in Section 2.6.
- Edge types: live types unverified; future containment/mentions and evidence-backed legal relationships only.
- Provenance strategy: current caller aggregates extraction without per-chunk references; target canonical chunk/span-linked assertions.
- Embedding strategy: no scoped code writes vectors to Neo4j; mandatory chunk vectors in Neo4j, optional entity/relation/community vectors only for defined retrieval use.
- Retrieval strategy: currently absent from query route; target semantic seeds, bounded traversal and source-aware fusion.
- Diagnostics: current external graph count/data endpoints are insufficient; read-only coverage/integrity/index report required.

### Verification
- Backend tests: scoped command collected zero tests; no backend suite pass claimed.
- Frontend lint/typecheck/build: all PASS after sequential retries (Section 2.4).
- Indexing dry-run: not available / not run.
- Indexing run: not run.
- Semantic retrieval test: not run against real corpus/providers.
- Graph retrieval test: no graph query path in scoped route.
- Hybrid retrieval test: mode currently only echoed; no hybrid implementation.
- Citation validation: static source fields identified; clickable passage grounding absent from current playground.

### Blockers / manual actions required
- Obtain authorized read-only access/configuration for actual application Turso, OCR-source mapping, Neo4j and served Ollama model; report capabilities/counts without exposing secrets. Credentials/service availability were not validated during this audit.
- Add non-mutating inventory and separate schema migration from startup before auditing configured remote state safely.
- Preserve persistent encryption key, take scoped backups and establish source identity/model provenance before transferring existing vectors.
- Implement backend-owned RAG interfaces to remove reliance on outside-scope `ai.*` modules.

### Commands to run the system
- Frontend: in `web/`, `bun run dev`; production `bun run build` then `bun run start`.
- Backend: from root, `.venv/bin/python -m backend.run` with configured dependencies/services; current startup writes schema/metadata.
- Indexing/repair: legacy command and its limitations in Section 11.2; target Neo4j indexing/migration/diagnostic commands remain to be implemented.
- Tests: frontend checks and scoped pytest command in Section 11.2; live acceptance/regression verification still pending.
