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

- [x] Record report timestamp, authorized org/project/source scope, redacted connection identifiers, database/server versions and reproducible read-only commands/queries. Evidence: `backend/inventory/reports/2026-10-18-live.{json,md}`, measurement window 09:02:36–09:02:46 UTC, all configured credential-owner-authorized stores; source before/after watermarks match; no cross-store snapshot claimed.
- [x] Measure actual source-document/OCR counts, application-document counts, canonical chunk counts and embedding totals/valid/missing/stale/invalid counts, separated by store, scope and generation. Evidence: 876 source records / 333 usable texts; 97 application documents across 3 measured scopes / 0 legacy chunk-vector rows; 96 distinct source-path candidate matches, 1 separate upload; no separate canonical chunk table. Expected future chunk counts are not applicable before canonical chunking, not invented as zero missing work. Retrieval-store counts/distributions are measured empty, not inferred from a local snapshot.
- [x] Measure stored vector dimensions/distribution and numeric validity; record model/provider/revision provenance and query-model compatibility. Evidence: full native `vector_extract` scan over 0 persisted vectors in all 3 projects; no stored generation/dimension/model distribution or unknown-provenance vector reuse. Actual query and OCR-excerpt probes both returned finite/nonzero 768-dimensional vectors; resolved `embeddinggemma:latest` digest `85462619ee721b466c5927d109d4cb765861907d5417b9109caebc4e614679f1` unchanged before/after; no vectors persisted.
- [x] Measure Neo4j node counts by label/type, edges by relationship type, chunk/entity vector coverage, vector-index configuration/state and source-provenance coverage with explicit numerator/denominator, plus dangling/duplicate records. Evidence: Neo4j 5.26.32 Community, default `neo4j` database globally 0 nodes / 0 edges, 0 vector indexes, 0 constraints, 2 ONLINE token lookup indexes; vectors/provenance 0/0, dangling/duplicates 0 in the verified empty store. No claim of 100% coverage or readiness, or of inspecting other deployments/volumes.
- [x] Classify migration records/counts with stable identifiers or a reproducible selector. Evidence: report disposition table and source/content-hash manifest: 0 vectors safe to copy / re-embed / repair / provenance-unknown; 333 usable source documents require initial canonical chunking/embedding, 543 excluded pending text/status repair; preserve 97 application records and reconcile 96 filename candidates. Preserve/exclude 13 invalid project mappings among 14 historical source configs. No destructive repair, cursor reset, re-OCR, data merge, migration or ingestion authorized/performed.
- [x] Record measured findings and report artifact location here. Evidence: versioned live JSON and human-readable summary under `backend/inventory/reports/`; same source manifest hash across two full scans. These are live configured databases, not the old local SQLite snapshot or UI defaults.
- [x] Record inventory review: **reviewer: project user in this conversation; date: 2026-10-18; decision: approved**, explicit response “yes sure” to the presented inventory/disposition. Scope: both configured Turso stores, all 3 measured application project scopes, default Neo4j database and probed Ollama model. Accepted: preserve existing records, 333 usable OCR texts eligible for later canonical indexing, 543 excluded from initial indexing, 0 vectors to copy; reconcile 96 candidate source links and preserve/exclude 13 invalid source-project mappings. Evidence: `backend/inventory/reports/2026-10-18-live.md` review record. Material corpus/model/schema changes require refreshed affected inventory/review; this approval does not authorize destructive operations.

**Current result (supersedes historical pending/blocked records below): Stage A COMPLETE — user review approved on 2026-10-18.** All configured Turso/Neo4j/model measurements, diagnostic checks and inventory review passed. **Stage B is eligible for a subsequent run**, subject to its own section/commit gates and safe migration requirements. This run records approval and stops; no Stage B implementation or database writes occur. See `backend/inventory/reports/2026-10-18-live.md` for scope, discrepancies, exclusions and non-destructive disposition.

**Latest audit-fix refresh:** all six audit findings corrected, **59 tests passed**, targeted Ruff/diff checks passed. `backend/inventory/reports/2026-10-18-audit-fixes.{json,md}` records the 09:31:37–09:31:58 UTC live run: `measurement_status=complete`, `measurement_issues=[]`, reconciled source counts and matching pre-count/post-scan watermarks. Regression comparison confirms the same connection identities, schemas, source/content manifest, application records, model digest and exclusions as the user-approved baseline. Existing approval still applies to that unchanged material inventory; no destructive operation or Stage B work performed.

**Current result: Stage B COMPLETE — 2026-10-18.** Backend now owns chunking, embedding calls, text staging and graph visualization reads with no sibling `ai.*`/LightRAG runtime dependency. Canonical control/staging tables (`document_sources`, `index_generations`, `canonical_chunks`) were added additively to the reviewed application store with a private pre-change snapshot; all original table rows were verified equal and no corpus ingestion, model probe or graph write ran. Readiness is evidence-based (legacy `ready` rejected; vector/graph capabilities stay false), and query modes return **409** until Stage C/D verification. **Stage C is eligible for a subsequent run** under its own model-dimension/provenance, Neo4j index/search and migration/rollback gates. Stop after this stage; see `backend/inventory/reports/2026-10-18-stage-b.md`.

### Stage C execution record — 2026-10-22 (in progress)

**C.1 selected before editing — model provenance:** refresh read-only inventory, resolve the served Ollama tag to its digest, measure dimensions and guard ingestion/query batches against digest drift. Preserve the existing provider API for text-stage callers. Acceptance: actual text is embedded with truncation disabled; malformed/missing model identity, digest drift and invalid vectors fail closed; focused tests, Ruff and diff review pass before the section commit. Refreshed live inventory is complete after Neo4j startup (first attempt encountered `ServiceUnavailable`); 333 eligible OCR contents and model digest are unchanged, 0 legacy vectors, empty Neo4j 5.26.32, 0 canonical chunks. Ten source metadata timestamps changed and application project metadata requires comparison before any corpus write. Live paraphrase acceptance additionally requires the human passage review in Section 9.1; do not substitute automated judgment for that gate.

- [x] C.1 model identity and dimension guard implemented in `embedding_service.py`; focused primitive suite **13 passed**, targeted Ruff and `git diff --check` passed; reviewed the complete section diff. No persistent model vectors or database writes.

**C.2 selected before editing — Neo4j vector storage and semantic search:** add a backend-owned, explicit vector CLI and scoped snapshot store using the verified Neo4j 5.26 `CREATE VECTOR INDEX` / `db.index.vector.queryNodes` APIs. Partition the candidate index by org/project/current canonical manifest/model digest so post-filtering a global top-k cannot starve tenants. Preserve canonical IDs/spans/model metadata; checkpoint valid batches and reject invalid/stale/foreign records. Default plan is read-only and embeds nothing; publication requires complete integrity and ONLINE index checks, and search rechecks live model/canonical identity. Acceptance: isolated tests cover scope, partial batches, corruption, model drift, empty input and retries; no legacy vector writes/copies, no dependencies, no grounded answer/API dispatch (Stage E).

- [x] C.2 implementation: `services/neo4j_vectors.py`, `scripts/index_vectors.py`; backend suite **104 passed, 1 opt-in skipped**, targeted Ruff/diff checks passed. Explicit disposable Neo4j 5.26 + actual Ollama check **1 passed**: real embeddings, ONLINE index/search, repeat-build skips only validated vectors, distinct tenant partitions, corrupted-vector repair, publish/withdraw rollback retains data and blocks reads. Found/fixed Neo4j returning uppercase `COSINE` in index metadata. No configured database writes in this increment. C.1 commit `fecabbf`.

**C.3 selected before configured writes — canonical corpus and unpublished vectors:** compare refreshed affected scope with approved inventory, retain private application backup, stage the existing valid OCR mapping and build only real canonical-text embeddings. Source content/eligibility/model/connection identities and all 97 legacy document records match approval; only ten source `updated_at` fields changed. A new unrelated empty project is excluded; the approved target project's measurements are identical. No legacy vectors exist to copy, and none are relabeled. Rollback is withdrawal of this partition's publication (verified on disposable Neo4j); retain all old application/source data and additive vectors, with no destructive replacement or corpus cutover. Acceptance: 333 texts reconcile with scoped canonical generation/chunk counts, exact provenance/vector integrity, ONLINE index, repeated build skips verified units, legacy non-indexing records unchanged; record real source paraphrase candidates and leave human review pending. C.2 committed as `08b4836`.

**C.3 promoted P0 blocker:** the real 350-word chunks can exceed the served model's measured `gemma3.context_length=2048`; Ollama returned HTTP 400 `the input length exceeds the context length` after 80 valid persisted vectors. Fix shared canonical chunking (all callers searched) with an explicit 1800 UTF-8-byte ceiling and a new recipe version, retaining exact source spans and prior generations; re-stage source idempotently, never truncate silently. Add multilingual/long-token coverage regression. Initial staging exceeded the shell's 240-second limit after 123 documents; the same command with 900 seconds resumed/reclaimed the interrupted lease and completed all 333 without duplicates. Configured Neo4j was stopped externally during the first build attempt; restarted the existing container and waited for startup, preserving its volume. No publication or cutover occurred.

- [x] **C.3a verified implementation checkpoint:** context-bounded `words-v2:350:40:utf8-1800`, source replay of all **333 documents / 10,417 current chunks**, checkpoint progress logs, frozen user-approved expected passages (`backend/evaluation/stage-c.json`) and reproducible vector/BM25 evaluation command. Original **97 document identities**, **14 source configurations**, all project/credential/conversation/message/query/vector/internal-vector rows preserved; only intended source progress and document indexing status/timestamps changed. Private pre-change snapshot: `backend/storage/backups/stage-c-before-2026-10-22.db`. Prior 333 text generations/7,475 chunks and 80 failed-recipe vectors retained. Backend **107 passed, 1 opt-in skipped**; targeted Ruff and diff checks passed. User approved the frozen expected passages; actual retrieval has not run. The background vector job remains active and unpublished. This checkpoint does **not** complete C.3 or Stage C.
- [ ] **C.3b live acceptance pending:** complete all 10,417 vectors, verify whole-partition integrity/ONLINE index and repeat-build reuse, run the frozen source-reviewed retrieval/BM25 evaluation, validate configured publication/withdrawal behavior and record final Stage C evidence. No Stage C completion claim until these checks pass.

**User-directed parallel-stage exception (this conversation):** after being informed that indexing is CPU-bound and that C still requires retrieval/integrity acceptance, the user explicitly requested “do stage d then in the mean while”. This supersedes the one-stage-per-run restriction only for independent Stage D implementation and isolated tests while C indexing runs. Keep stage/section commits separate. Do not mark C complete, publish an incomplete vector/graph index, run competing live enrichment, or waive C/D live retrieval and human-evidence gates. The C.3a checkpoint is committed before D implementation; C.3b remains open.

### Stage D parallel implementation record — live acceptance pending

**D.1 selected before editing — source-backed extraction boundary:** reuse the existing Ollama generation client and graph model configuration; replace its unused schema with bounded typed entities and explicit relationship quotations. Independently validate exact canonical text/spans, endpoint types, explicit relation cues and negation; no inferred co-occurrence legal relationships or silent fallback. Resolve the extractor model revision and recipe, reject drift and retain separate timeout/provider/parse/evidence failure codes. Resolve only exact full AIR Supreme Court citations across documents; keep other names document-scoped to avoid merging namesakes. Acceptance: isolated tests reject fabricated/negated/reversed/foreign evidence, prove exact offsets, all evidence preservation and deterministic identity, and show malformed/timeout/model drift failures. No live extraction/model generation or configured graph writes; Stage C job continues. C.3a checkpoint committed as `071b2b4`.

- [x] D.1 implemented in `services/graph_extraction.py` and existing `llm_client.py`: exact source occurrences, all evidence spans, scoped identities, typed quote-backed assertions, model/recipe provenance, explicit errors and bounded model timeout. Backend suite **123 passed, 1 opt-in skipped**; targeted Ruff and diff checks passed. Semantic/legal interpretation remains an extraction candidate with explicit method, not a substitute for corpus review. Conservative explicit-cue/negation checks may reject legitimate indirect/complex legal statements; these are visible failures, not invented repairs. Live Stage D extraction remains unrun. Stage C checkpoint observed processing at 4,000 vectors, no error.

**D.2 selected before editing — evidence store and graph retrieval:** persist extractor-versioned entities/assertions and each supporting canonical chunk/span in a separate graph generation referencing Stage C's existing chunk nodes. Atomic per-chunk writes, hash-validated cached extraction, durable attempts/errors, repair/idempotency, full provenance integrity and explicit empty/partial states. Implement semantic-seeded graph expansion through shared typed entities and supported assertions with fixed hop/fanout/evidence budgets, scope/generation checks, deduplication and cycle bounds. Expose a default-no-write CLI; live operations require a published, complete vector generation. Acceptance: isolated real-Neo4j fixtures (no local model requests) prove connected evidence beyond seeds, canonical source resolution, cross-tenant isolation, retry/idempotency, corruption detection/repair and failure/empty states; no configured graph mutation or GraphRAG-ready claim. D.1 committed as `a28c227`.

- [x] D.2 implemented in `services/evidence_graph.py`, `scripts/index_graph.py`, tests and runbook. Backend **132 passed, 2 opt-in skipped**; disposable Neo4j suite **3 passed** (one real storage/traversal scenario plus two unit checks); broad scoped Ruff/diff checks passed. The real-store fixture proves one vector seed expands to a second document via a source-backed typed assertion, exact evidence resolution, tenant isolation, bounded cycles, idempotency/retry, corrupted-span repair and publication withdrawal. Model output/vectors in this fixture are explicitly synthetic, not corpus-quality evidence. Configured source plan **333 documents / 10,417 chunks** passed without model/graph calls. Graph model availability/digest checked by tags only; no live generation or D graph writes. Report: `backend/inventory/reports/stage-d-parallel.md`.
- [ ] **D live acceptance remains pending:** C.3b must pass before live enrichment; then validate actual configured-model extraction/coverage and a human-reviewed cross-document graph retrieval set before publication or Stage D completion. Current explicit predicate validator is English-only and conservative; regional-language/indirect assertions remain unsupported rather than fabricated. C progress at handoff: **4,704 / 10,417**, processing, no error. Parallel development is complete; Stage E has not started.

### Stage E parallel implementation record — C/D/E live acceptance remains OPEN

**User-authorized continuation:** the user approved independent Stage E development while the earlier jobs/gates remain open, explicitly requiring a statement/log to return and complete C, D and E tests. The bounded parallel exception therefore also covers E implementation and isolated checks; it does not permit premature publication, live-generation load during C indexing or completion claims. **Mandatory return-to-verification log:** `backend/inventory/reports/verification-return.md`; keep all unmet live checks unchecked in subsequent handoffs.

**E.0 selected scope — durable handoff:** record the explicit return-to-tests instruction and pending C/D/E criteria before E code changes. Documentation-only acceptance: checklist links correct, pending tests distinguished from evidence, diff reviewed and section committed. D.2 committed as `49c88a4`.

**Planned bounded E increments:** E.1 published-generation retrieval dispatch, reciprocal-rank hybrid fusion and whole-passage evidence budgeting; E.2 bounded grounded generation with actual provider/fallback and validated citations/query-run outcomes; E.3 Flask contracts, authorized passage resolution, conversation isolation and meaningful API checks; final runbook/verification handoff. Complete/check/commit one increment before the next. No frontend work or C/D/E live acceptance is inferred.

**E.1 selected before editing:** reuse C/D's actual Neo4j retrieval paths and extract their existing publication guards into shared checks; dispatch vector/graph/hybrid without silent fallback, fuse ranks rather than incompatible scores, preserve canonical provenance and graph paths, and select whole-passage context under a conservative serialized-byte/token ceiling. Graph/hybrid context must retain an actual connected evidence path, not just its vector seeds. Add a read-only published-retrieval readiness projection and post-generation freshness guard for the next increment. Acceptance: isolated tests prove mode dispatch, scope checks, rank deduplication, connected-context budgets, unavailable-mode refusal and stale generation detection; relevant existing C/D tests remain passing. No real generation or corpus publication. E.0 committed as `67b6f15`.

- [x] E.1 implemented in `services/retrieval.py` and shared C/D publication guards. Real store calls remain mode-specific; hybrid uses reciprocal-rank fusion (`k=60`), not addition of cosine/path scores. Context preserves whole canonical passages and complete graph paths under a serialized **5,000-byte** evidence budget. Missing/stale/foreign evidence and unpublished requested modes fail explicitly; no fallback to vector-only graph/hybrid. Read-only readiness and generation rechecks support E.2/E.3. Backend **142 passed, 2 opt-in skipped**, targeted Ruff/diff checks passed; no live query generation/publication. C observed processing at **5,888 vectors**, no error. C/D/E live gates in `verification-return.md` remain open.

**E.2 selected before editing — grounded generation and outcomes:** retain the configured platform → Ollama direction with bounded requests/output and explicit actual provider/model/fallback metadata. Feed only selected canonical passages as untrusted JSON; require structured answered/insufficient-evidence output and validate all used source labels against inline markers. Produce stable source IDs, exact excerpts/spans/pages and authorized passage URLs, distinguish candidates from cited sources, and enforce message/prompt budgets. Validate conversation org/project/user before retrieval, recheck index generation before returning, and persist truthful query-run outcomes (never completed for missing/insufficient/failed evidence). Acceptance: source/citation/prompt/provider/fallback/abstention/freshness and ledger tests with controlled clients; no live generation or inferred faithfulness pass. E.1 committed as `3834573`.

- [x] E.2 implemented in `services/{grounding.py,query_service.py,llm_client.py}`. Question budget **1,024 UTF-8 bytes**, prompt ceiling **7,000 bytes**, output **1,024 tokens**; SDK timeout **60s / one retry**, fallback timeout **60s** with explicit provider/model/reason. Stable canonical citation IDs and contextual `[S1]` labels are separate; invalid/missing/invented references fail closed, while model/no-context abstention persists `insufficient_evidence`. Invalid conversations are rejected before retrieval; changed indexes after generation fail rather than return stale answers. Backend **165 passed, 2 opt-in skipped**, targeted Ruff/diff checks passed. Tests use controlled SDK/HTTP/model responses and local SQL; source entailment and real provider/corpus quality remain unchecked in the mandatory return log.

**E.3 selected before editing — Flask contracts and sources:** wire the existing query route to E.1/E.2; preserve `answer`, `mode`, `project_id`, `query_run_id` and additive structured sources/diagnostics. Define **new** authenticated `GET /api/projects/<project_id>/passages/<chunk_id>` for canonical text, with exact ID/hash/span/page integrity, tenant/project/document joins and explicit historical-generation labeling. Use published retrieval readiness on existing document/status GETs; no GET schema writes or model generation. Validate actual forwarded authentication and scoped conversations in Flask tests. **Promoted P0 trust-boundary fix:** the existing shared auth helper accepts identity headers when no internal secret is configured; exposing source text/answers through that behavior would create a concrete disclosure path. Require configured `BACKEND_INTERNAL_SECRET` on query/passage routes (503 when missing), reusing the existing secret check and org-scoped project lookup; no broader auth/role redesign. Acceptance: real local-SQL/Flask tests for successful citations/source resolution, foreign projects/orgs/users, malformed requests, corrupt/historical sources, missing/partial indexes and generation failure; no real LLM requests. E.2 committed as `7f52f1e`.

**Return-to-verification checkpoint:** C's background build finished all **10,417 vectors** in the frozen partition, with final canonical consistency check and `verified_unpublished` output. The first real evaluation is preserved at `backend/inventory/reports/stage-c-vector-evaluation-01.json`: exact case lookup passes at rank 1; both frozen paraphrase passages miss top 8. No publication or live D enrichment is permitted until required retrieval cases pass. The user's `dd25c62` formatting commit includes the E.3 API/source implementation; preserve it. Current backend pytest **175 passed, 3 opt-in skipped**. Formatting moved 15 existing `BLE001` suppression comments off their diagnostic lines, creating 30 Ruff errors. **Selected bounded prerequisite fix before editing:** move only those annotations to the caught exception type; retain all error handling/formatting, verify AST equivalence and passing scoped Ruff/tests, then commit before retrieval investigation. The frozen evaluation labels/queries are not relaxed to manufacture a pass.

- [x] Formatting prerequisite repaired: all **10 changed Python files are AST-equivalent to `dd25c62`**, scoped Ruff passes, Black check leaves all ten files unchanged, and `git diff --check` passes. Existing backend tests on the formatted code: **175 passed, 3 opt-in skipped**; no behavior changed and no new test is needed for comment placement. Failed live retrieval evidence is retained, not overwritten; C/D/E live acceptance stays open.

### Stage B execution record — 2026-10-18 (complete)

**B.1 selected before editing — first-party primitives and read-only graph surface:** implement independent backend-owned exact-span chunking, retrieval value/prompt types, validated Ollama embedding calls and scoped Neo4j visualization reads. Replace their scoped callers; ingestion ownership is completed in B.3 after its metadata dependency exists. Do not copy/read sibling implementations. Acceptance: primitive/provider/span tests pass, graph GETs perform no ensure/create calls, no added dependencies. No vector/graph indexing or retrieval acceptance is claimed before Stages C/D/E.

- [x] B.1 implemented: `services/rag.py` exact source spans, bounded word chunks preferring sentence/paragraph ends, source-grounded prompt/value type; `embedding_service.py` actual bounded Ollama POST with count/768D/finite/nonzero checks; `graph_store.py` scoped READ-session bounded visualization, escaped static HTML, no ensure/create methods. Graph/query/vector callers use backend modules. Factory imports are lazy so importing primitives does not load credentials/startup/sibling modules. Ingestion/backfill callers remain explicitly pending B.3. Full backend suite **67 passed**, targeted Ruff and `git diff --check` **PASS**; eight new primitive checks cover span coverage, malformed vectors, provider payload and read-only graph scope. No live writes or dependency additions.

**Stage B migration/identity plan:** add control-plane source mappings, immutable canonical-text/chunk generations and per-generation retry state; preserve existing tables/vectors/documents. Reuse exactly one unclaimed legacy filename match within org/project; reject ambiguous matches. Stable source namespace uses endpoint/table/ID-column, not credential or source-configuration UUID. Source text is retained as staging input, not a new Turso vector retrieval store. Explicit migration command must support read-only planning, backup-before-apply and repeatability; remove app-startup writes/metadata relabeling. Test migration/rollback preservation on isolated databases before any configured-store application. A rollback stops writers and restores the pre-migration backup; additive staging tables may be retained without changing legacy reads. Do not drop legacy data or automatically index the approved 333 texts in Stage B.

**Planned next bounded sections (not started):** B.2 additive migration/identity/state repository plus no-write planning; B.3 integrate source/upload canonical ingestion, durable failures/replay, source/page spans, formal document/corpus readiness and dependency-boundary tests; B.4 final exit evidence/runbook/handoff. Each section requires checks/diff review and successful Conventional Commit before the next begins. Preserve untracked `backend/docker-compose.yml`.

**B.2 selected before editing:** add `document_sources`, `index_generations`, `canonical_chunks` control/staging tables with unique scoped source identity, immutable exact-span generations and persistent attempts/failures. Explicit migration only, no startup writes/relabeling; default CLI plan uses confirmed read-only transport, apply requires a new private backup path. Acceptance: repeated migration/ingestion is idempotent; legacy IDs/metadata preserved, ambiguous adoption rejected, cross-scope documents rejected, changed content/recipe invalidates generation, failed/processing work retries, exceptions roll back; dry-run database bytes unchanged. B.1 committed as `fe7abb1`.

- [x] B.2 implemented in `db/{index_schema.sql,indexing.py,connection.py}`, `scripts/migrate.py`. Three additive tables; scoped unique source mapping, content/metadata/recipe generations, exact spans/page intersections, attempts/safe failures and atomic short leases with expired-worker invalidation. Replays preserve ID/generation/chunk count, failed/expired work retries, changed text/model recipe creates a distinct generation without deleting old text. Legacy filename adoption rejects ambiguity or an already-claimed source. App factory no longer migrates; migration no longer rewrites embedding metadata, and DB context rolls back exceptions. Default migration/ingestion planning uses confirmed read-only connections; explicit apply requires an exclusive 0600 table-data snapshot. Stop writers before backup/apply; backup does not preserve indexes, which must be recreated by the retained schema on restore. Isolated libSQL tests cover migration twice from legacy tables, backup row equality/permissions, no-write plans, idempotency, scopes, retries and rollback: full suite **74 passed**, targeted Ruff/diff **PASS**. Configured live `python -m backend.scripts.migrate --env-file backend/.env` read-only plan **PASS**; no live schema applied yet, no ingestion run. Fixed 60s text-only lease ceiling/upgrade is marked `shortcut:`.

**B.3 selected before editing:** replace the old ingestion/backfill sibling imports with canonical text staging and explicit not-yet-verified retrieval. Replay OCR through confirmed read-only paged reads, preserving full source row/URL and native PDF page spans; ignore legacy forward cursors so failed rows remain retryable. Retain ledger failures and add scoped document/corpus readiness to Flask, with exact generation/span/hash checks and explicit unavailable retrieval modes. Add a default-dry-run source batch CLI; source creation must no longer start unreviewed ingestion in a daemon thread. Uploads use scoped byte identity, retain raw files and return text readiness. Acceptance: actual source replay after an advanced cursor retries the same document; dry-run writes neither database/status/files; chunk-only never reports vector/graph ready; changed recipe/corrupt chunks/stale worker invalidate readiness; factory/routes import without sibling services or startup writes. Boundary tests inspect all scoped Python and web manifests. B.2 committed as `646585a`.

- [x] B.3 implemented: first-party `ingestion_service.py` stages exact existing OCR/native PDF text only; source metadata/URL and available page intersections survive canonical chunking. Source reads use server-approved/local read-only transport, validate non-null unique IDs, Python whitespace eligibility, bounded keyset batches and full replay independent of old cursors/config UUIDs. Durable generation attempts/failures and source error IDs are safe; identity conflicts require review. `scripts/index_source.py` defaults to dry-run and resolves org/project/source before processing. Upload retries share byte/filename identity and retain raw files; unsupported/scanned PDFs get explicit durable text failures without re-OCR. Source creation only saves configuration. Unsafe legacy backfill now exits with a clear retirement reason.
- [x] B.3 readiness: document responses plus `GET /api/projects/<project_id>/indexing/status` expose generation/recipe, exact source/hash/span/page integrity counts, timestamp, separate capabilities and structured retry failures; legacy bare `ready` is not accepted as evidence. Corpus includes every scoped application document, not only successes. Readiness uses four batched reads rather than per-document remote queries. Required retrieval stays unavailable (409 for vector/graph/hybrid; 400 invalid modes), without LLM calls, Turso vector writes or false completed query runs. No vector/GraphRAG publication path exists before C/D/E. Read-only factory test, actual upload/source replay, changed model/corrupt chunk/interrupted/partial graph tests, source CLI no-write test and AST/manifest dependency checks pass. Full suite **83 passed**, targeted Ruff/diff **PASS**. No `ai.*` or LightRAG runtime import remains; no dependencies added. Fixed text-only lease/full-source replay/deep staging validation ceilings are marked `shortcut:`. Graph extraction, Neo4j vectors/search and real answer dispatch remain their planned later stages.

**B.4 selected before final verification:** tighten backup/apply to one native `BEGIN IMMEDIATE` transaction so the private backup observes exactly the pre-migration snapshot and a failed migration rolls back every change. Add rollback regression; store private backup outside Git under `backend/storage/backups/`. After checks, apply only additive Stage B metadata to the reviewed application DB, compare all original table rows against backup, verify reapplication and scoped live pending readiness/health with no corpus ingestion. Verify the one valid configured OCR mapping can preview through stored credentials; credential/access failures block only their unmet criterion and must be reported. Add runbook/exit evidence and final checklist updates. No Stage C writes/indexes/model publication or OCR rerun. B.3 committed as `06fcdb5`.

- [x] B.4 implemented/verified: `scripts/migrate.py` now takes the backup and applies additive DDL inside one native `BEGIN IMMEDIATE` transaction, so the 0600 snapshot equals the exact pre-change state and any failure rolls back all changes. `backend/storage/backups/` is Git-ignored (only `.gitignore` tracked). Isolated regression simulates a failing migration and confirms both DDL and data are restored while the snapshot is retained. Live exit evidence: read-only plan; additive apply with `stage-b-before-2026-10-18.db`; explicit reapply with `stage-b-repeat-2026-10-18.db`; post-reapply/preview/Flask comparison confirmed all **10 original tables' rows** byte-equal to the first snapshot (3 projects, 97 documents, 14 sources, 0 chunk vectors) with the 3 new tables empty. The single valid configured OCR mapping decrypted via stored credentials and produced a no-write preview of **333 usable rows, 0 failures, 27 excluded**. Live readiness reports **3 projects / 97 pending** with no capabilities; factory/health/index-status pass and hybrid query returns **409** with no answer or query-run write. Runbook `backend/README.md`; exit report `backend/inventory/reports/2026-10-18-stage-b.md`. Final full suite **84 passed**, targeted Ruff/diff **PASS**; no dependency added. Rollback requires no data deletion (stop workers, redeploy previous backend, keep additive tables). B.4 commit hash in user handoff.

**Stage B handoff (complete):** scope = backend ownership, stable identity, canonical versioned chunks, retained source metadata, indexing ledger/retry state and truthful readiness — no Neo4j vectors, graph retrieval, answer dispatch or frontend work. Sections/commits: B.1 `fe7abb1`, B.2 `646585a`, B.3 `06fcdb5`, B.4 (final). Exit criteria → evidence table in the Stage B report; live/check commands and outcomes recorded there. Changed/new files: backend-owned `services/{rag.py,embedding_service.py,graph_store.py,ingestion_service.py}`, `db/{index_schema.sql,indexing.py,connection.py}`, `scripts/{migrate.py,index_source.py,backfill_embeddings.py}`, routes, tests, runbook and this report. Inventory/migration/readiness: additive control/staging tables applied to the reviewed application store; source/application data unchanged; readiness now evidence-driven. Blockers: none for Stage B; credentials/access for the OCR source were available. Deferred: full-source replay scheduling, text-lease renewal, per-read integrity proofs, Neo4j vectors/graph, answer dispatch, frontend. Next-stage eligibility: **Stage C eligible**, subject to its own model-dimension/provenance validation, Neo4j index/search implementation and separately verified migration/rollback before corpus cutover. Stop after Stage B; `backend/docker-compose.yml` remains preserved/excluded.

#### Stage A execution record — 2026-10-18 (complete)

**A.11 selected bounded audit-fix subset (before refresh):** record a new read-only live inventory using all corrected paths, preserve the original approved artifacts, compare material scope/content/model/eligibility against that approval, and run final regression/Ruff/diff checks before committing the evidence. Acceptance: all live measurements complete with no measurement issues; source counts/watermarks and global/scoped vector coverage reconcile; changed connections/content/model/eligibility require renewed affected review rather than automatic approval. No app startup, ingestion, migration or Stage B work. A.10 committed as `25f3b1b`.

- [x] A.11 live refresh completed and versioned without overwriting original evidence. Exact command: `.venv/bin/python -m backend.scripts.inventory --env-file backend/.env --all-configured --output backend/inventory/reports/2026-10-18-audit-fixes.json`; expected exit 2 retains the diagnostic review gate, while the report confirms complete measurements/no issues. Full source manifest and all material comparison fields match the approved snapshot. Existing 333/543 eligibility/disposition and 0-vector migration plan remain valid; no renewed approval is inferred for changed data.
- [x] A.11 final checks: `.venv/bin/python -m pytest backend -q -o addopts='' -p no:cacheprovider` **59 passed**; `.venv/bin/ruff check backend/inventory backend/scripts/inventory.py backend/tests --no-cache` **PASS**; `git diff --check` **PASS**. Tests include runtime completion validation against the new live artifact and exact baseline/refresh comparison, not reconstructed summary counts. Independent-read limitation is explicitly marked with a `shortcut:` ceiling/upgrade comment; no snapshot guarantee is fabricated.

**Audit-fix handoff:** finding 1 + 4 / A.6 `0db349a`; finding 2 / A.7 `39ed8a8`; finding 3 / A.8 `093cc8b`; finding 5 / A.9 `9c1293c`; finding 6 / A.10 `25f3b1b`. Each section's tests/checklist evidence/diff review preceded its successful Conventional Commit. A.11 evidence commit hash is reported in the user handoff. All six findings resolved; no dependencies added. New/final section files: corrected live report JSON + readable summary, baseline-comparison regression, diagnostic README and this checklist; original approved artifacts preserved. `backend/docker-compose.yml` remains pre-existing untracked work, preserved/excluded. Stage B eligibility remains subject to its own scope, migration/rollback requirements and refreshed affected inventory if corpus/model/schema changes. Stop after this Stage A repair run.

**A.10 selected bounded audit-fix subset (before editing):** finding 6, remove the unused `confirmed_reads` initialization/increment after whole-tree caller search found only those two writes. Acceptance: delete exactly the unused counter, existing Hrana approval/refusal tests pass, targeted Ruff/diff review and section commit; no new test for a trivial dead-state deletion. A.9 committed as `9c1293c`.

- [x] A.10 implemented/verified: removed two unused counter writes; server-side read-only checks and stream cleanup unchanged. Existing transport tests **5 passed** (32 unrelated tests deselected), targeted Ruff **PASS**, `git diff --check` **PASS**. No dependency added/removed.

**A.9 selected bounded audit-fix subset (before editing):** finding 5, preserve existing secret-safe access reasons consistently in scoped/full diagnostics. Move the existing redacted exception formatter to the standalone SQL module, reuse it in both callers, and test missing source URL versus missing token without real connections; arbitrary exception messages must remain excluded. Acceptance: both paths preserve enumerated reasons, existing no-leak tests pass, relevant checks and section commit. A.8 committed as `093cc8b`.

- [x] A.9 implemented/verified: shared `backend.inventory.sql.blocked` replaces the duplicate formatters; scoped and full CLI paths retain `AccessBlocked.reason` and optional underlying error type while excluding raw messages. Scoped pytest **58 passed**, targeted Ruff **PASS**, `git diff --check` **PASS**. Full-path regression tests distinguish missing OCR URL from missing token without network calls; existing arbitrary-error redaction tests pass.

**A.8 selected bounded audit-fix subset (before editing):** finding 3, one Python `str.strip()`-based text predicate for source counts, eligibility and source/chunk text checks. Replace SQL-trim-derived OCR counts with batched read-only Python counts, publish candidate SQL plus its exact post-filter and eligible source ID hashes, and test tab/newline/Unicode/NUL inputs through scoped and full inventory paths. Acceptance: counts/classifications/reproducible selection agree, no raw OCR in reports, no database writes; targeted checks and commit. A.7 committed as `39ed8a8`.

- [x] A.8 implemented/verified in shared `has_text`, scoped source counts, full source status counts/classification and selector post-filter/ID hashes. Counts and fingerprint passes must reconcile. Scoped pytest **56 passed**, targeted Ruff **PASS**, `git diff --check` **PASS**. Regression fixture covers spaces, tabs/newlines, Unicode whitespace, null text and text beginning with NUL; scoped/full counts, classification and selected IDs agree. Original approved artifacts remain frozen; new live evidence will use the corrected selector contract.

**A.7 selected bounded audit-fix subset (before editing):** finding 2, align explicit dotenv/environment precedence with `backend.app.config` without importing startup. Acceptance: conflicting database URL/token/model settings select dotenv values, unset dotenv values preserve the shell fallback, CLI help/README describe the rule, targeted tests and checks pass before commit. A.6 committed successfully as `0db349a`.

- [x] A.7 implemented/verified: CLI now overlays defined dotenv values on the shell environment, matching existing backend precedence; null dotenv entries preserve the shell fallback. CLI help/README updated. `test_inventory.py` **37 passed**, targeted Ruff **PASS**, `git diff --check` **PASS**. Regression test drives the actual CLI with conflicting URL/token/model values and intercepts the report builder, so no startup or remote connection runs.

**A.6 selected bounded audit-fix subset (before editing):** findings 1 and 4, inventory completion and source consistency. Start the source watermark before counts, reconcile scanned/global counts and classifications, reject unscanned orphan vectors, project blockers and unknown required vector coverage. Preserve repair/exclusion findings rather than treating data defects as permission for writes. Acceptance: regression tests reproduce all rejected cases and the zero-vector complete case; source changes between counts/scan block completion; tests/Ruff/diff review and a Conventional Commit before the next subset. Remaining audit fixes and refreshed live evidence follow within Stage A only; existing approved snapshot remains frozen.

- [x] A.6 implemented/verified in `backend/inventory/live.py` and `backend/tests/test_live_inventory.py`: explicit `measurement_issues`, global/scoped/scanned/classified vector reconciliation, project-blocker/staleness/generation rejection, document total check, source counts/status/ID reconciliation, and pre-count watermark. Scoped pytest **54 passed**, targeted Ruff **PASS**, `git diff --check` **PASS**. Initial Ruff test-fixture mutable-class-field finding fixed before final checks. Regression coverage includes every audited false-completion case plus an actual count/scan change; no live data writes or snapshot edits.

**A.5 selected bounded subset — user-review closure:** record the explicit approval received after the live report was presented; update the review gate and next-stage eligibility without altering frozen measurements or starting Stage B. Acceptance: reviewer/date/scope/decision and exclusions recorded, original machine-readable measurement snapshot preserved, documentation diff checked/reviewed and committed. A.4 commit `de5c00f` succeeded; final Stage A tooling verification was 45 passing tests and passing targeted Ruff/diff checks. This documentation-only approval increment does not require rerunning unchanged live probes or tests.

**Final Stage A handoff:** A.1 `bc78080`, A.2 `f1a2360`, A.3 `46eb03b`, A.4 `de5c00f`; all scoped implementation increments successfully committed. A.5 approval commit is reported in the handoff rather than a self-referential extra commit. Every Stage A exit criterion now passes, including the user's review. No service-access blocker remains. Known discrepancies are inventoried exclusions/repair work for the later bounded stages, not silently waived readiness. `backend/docker-compose.yml` remains pre-existing untracked work and is preserved/excluded from this increment.

**A.3 selected bounded subset (2026-10-18, scope announced before editing):** replace the incompatible remote PRAGMA guard with Hrana server-side statement description (`is_readonly=true` required before execution), retain local read-only protection, add denial/transport tests, run live identity discovery and commit this verified increment before extending the inventory report. Acceptance: no unchecked remote executes, no startup/ingestion/write SQL, no token forwarding across origins, no credentials in evidence. User explicitly authorized direct OCR environment access through `OCR_TURSO_DB` / `OCR_TURSO_DB_TOKEN`, plus reading `dataset-api/main.py` solely to confirm the source schema; no dataset service was imported, started or modified.

- [x] A.3 live server-described discovery succeeded: `/tmp/opencode/inventory-scopes-hrana.json`, timestamp `2026-10-18T08:56:45Z`, same application connection fingerprint as the earlier failed attempt. Found 3 projects and 14 `turso_ocr` source configuration records. Historical PRAGMA failure is superseded by successful read-only statement description/execution, not bypassed by unchecked SQL. Raw tokens, URLs and encrypted fields were not emitted. `backend/docker-compose.yml` is pre-existing untracked user-requested work and is excluded from this section's commit.
- [x] A.3 checks: scoped backend pytest **36 passed**; targeted Ruff **PASS**; `git diff --check` **PASS**. New transport tests require server approval before execution, reject false/missing read-only flags, reject cross-origin routing and server describe errors, and verify stream cleanup. Live Hrana schema/identity reads also passed. Final diff/new-file review and successful section commit are reported in the handoff.

**A.4 selected bounded subset (scope recorded before editing):** add explicit `--all-configured` read-only inventory for the credential-owner-authorized application database, OCR source from `OCR_TURSO_DB` / `OCR_TURSO_DB_TOKEN`, deployed Neo4j default database, and served Ollama model. Discover actual org/project/source scopes and schemas, record watermarks, source content fingerprints and status exclusions, reconcile legacy filenames conservatively, measure vector/graph integrity and migration classifications, save a secret-free report, test meaningful failure/empty-store paths, and commit evidence. Acceptance: no startup/index/ingestion/schema writes, no arbitrary invented scope, no unknown-provenance copying, no empty-store denominators presented as readiness, full report presented for user review. A.3 commit `46eb03b` succeeded before A.4 began.

**A.4 measurement handoff — technical inventory complete; review subsequently approved in A.5:**

| Stage A exit criterion | Evidence / result |
|---|---|
| Actual source/application scoped counts and reconciliation | **PASS**: live report, source manifest over all 876 rows; 333 usable OCR texts; application 3 projects / 97 docs / 0 chunk vectors; 96 candidate source matches, no repeated path groups, 1 unmatched upload preserved. |
| Stored dimensions/model provenance, served-model compatibility | **PASS for measured current state**: no persisted vectors or generations to classify as compatible; real query/source probes both 768D, finite/nonzero, served digest recorded and stable. Corpus not indexed; no semantic retrieval claim. |
| Neo4j type/index/vector/provenance coverage and integrity | **PASS for measured empty database**: global 0 nodes/edges, no vector index, 0/0 evidence/vector denominators, no dangling/duplicate records. Future populated schema must be verified in its implementation stage. |
| Non-destructive eligibility classification | **PASS (report only)**: copy 0 existing vectors; initial chunking/embedding for 333 eligible source texts; exclude/preserve 543 other source rows; preserve application docs and 13 orphaned source project mappings. |
| No-write/startup behavior and relevant checks | Tooling tests include server pre-description/refusal, read-only SQLite/hash, source scope, pagination, changed model digests/dimensions, source/app reconciliation, graph empty/nonempty and independent service failure. Exact final check totals/commit hash are recorded in handoff. |
| Required inventory reviewer/date/scope/decision | **PASS**: project user approved the presented inventory/disposition with “yes sure” on 2026-10-18; scope/exclusions recorded in A.5 and the readable report. |

**A.4 changed/new paths:** `backend/inventory/live.py`, `backend/scripts/inventory.py`, `backend/inventory/report.py`, `backend/inventory/README.md`, `backend/tests/test_live_inventory.py`, both live report artifacts and this checklist. Existing untracked `backend/docker-compose.yml` preserved/excluded. Schema/data/readiness mutations: **none**. Graph/vector/ingestion implementation remains for later stages; frontend unchanged. See report/README and Section 11 for exact commands and environment variables; `OCR_TURSO_DB` / `OCR_TURSO_DB_TOKEN` are now implemented direct diagnostic inputs only.

- [x] A.4 final checks: `.venv/bin/python -m pytest backend -q -o addopts='' -p no:cacheprovider` **45 passed**; `.venv/bin/ruff check backend/inventory backend/scripts/inventory.py backend/tests` **PASS**; `git diff --check` **PASS**. Initial 36-test/44-test runs passed; Ruff import formatting/late-binding findings were corrected before final checks. Versioned live evidence passes manifest fingerprint, count reconciliation, empty-store/readiness and model-digest consistency assertions. Two complete read-only live runs produced the same source manifest; no failed live service measurement remains. Frontend checks not rerun for backend-only diagnostics. Final diff/new artifact review and A.4 Conventional Commit hash are in the user handoff.

**A.1 selected bounded subset:** standalone read-only inventory transport, legacy SQL measurements, source mapping verification, graph schema discovery and transient model probe (Sections 2.7 / 11.3, tooling only). Scope and acceptance were announced before implementation: no app/startup or write paths, missing schema and unknown provenance explicit, regression tests and usage documentation. This is an incremental Stage A deliverable, not completion of Section 2.7 or permission to begin Stage B.

- [x] Implement standalone `backend.scripts.inventory`, owned by `backend/inventory/`, without `backend.app`, `ai.*` or LightRAG imports. Native Turso `vector_extract` decoding, complete paged legacy vector scan, source-table mapping from the existing scoped data-source row, read-only graph discovery and optional non-persisted Ollama probe are implemented.
- [x] Enforce SQLite file `mode=ro`, require confirmed SQL `query_only`, reject write/script/extension calls at the query boundary, use Neo4j read transactions and redact driver messages/connections. Require deployment read-only credentials as documented; READ_ACCESS alone is not authorization.
- [x] A.1 verification: `.venv/bin/python -m pytest backend -q -o addopts='' -p no:cacheprovider` **29 passed**; targeted `.venv/bin/ruff check backend/inventory backend/scripts/inventory.py backend/tests/test_inventory.py` **PASS**; `git diff --check` **PASS**. Initial 25-test run passed; initial Ruff findings were fixed before the final checks. Startup isolation is tested with forbidden-import interception; actual local database hash/read-only rejection and read-transaction-only Neo4j mocks are tested. Live read-only permission enforcement is not claimed from mocks.
- [x] A.1 final staged diff (all seven new files plus checklist evidence) reviewed; Conventional Commit `bc78080` succeeded. No unrelated work or credentials staged.
- [x] A.2 live measurements/review follow-up completed through A.3–A.5: scopes discovered, all configured stores measured, discrepancies and empty-store coverage documented, user review approved. Original A.2 access-failure evidence below remains historical.

**Implemented interface:** `.venv/bin/python -m backend.scripts.inventory --help`. Exact commands, configuration, read-only protections, classification rules and limitations: `backend/inventory/README.md`. New report paths are required; exit 2 intentionally keeps the migration/review gate closed. No runtime ingestion/query behavior or existing data is changed by this subset.

**A.2 selected bounded subset (before further editing):** execute identity discovery using the explicit existing `backend/.env`, improve secret-free access-failure reasons when discovery failed with an opaque `ValueError`, and record evidence/blockers. Acceptance: preserve read-only behavior and previous reports; expose only enumerated failure reasons; test config failures; no invented scope or counts; report every Stage A exit criterion and stop if required access remains blocked.

- [x] A.2 tooling/evidence subset verified: enumerated access reasons added; same scoped pytest command **32 passed**, targeted Ruff **PASS**, `git diff --check` **PASS**. Previous evidence was preserved; the retry used a new filename. Deployment read-only confirmation still failed; no schema/row read, source decrypt/connect, Neo4j query, model probe, startup, migration or indexing was executed by the discovery command.
- [x] Record attempted live command and secret-free artifact: `.venv/bin/python -m backend.scripts.inventory --env-file backend/.env --discover-scopes --output /tmp/opencode/inventory-scopes-20261018-retry.json`; report timestamp **2026-10-18T08:38:56Z**, connection fingerprint `sha256:6e5eb4f1f01a90d8`; versioned artifact `backend/inventory/reports/2026-10-18-access-blocker.json`. Initial attempt `/tmp/opencode/inventory-scopes-20261018.json` recorded an opaque `ValueError`; retry identified `query_only_unavailable`. Exit 2 is the command's documented closed-gate result, not a completed inventory. Neither attempt measures an empty corpus or proves credential validity.

**Historical A.2 exit-gate handoff (superseded by A.3/A.4 above):**

| Exit criterion | Evidence / result |
|---|---|
| Actual source/application scoped document, chunk and vector counts | **BLOCKED**: identity discovery stopped before schema/row reads; org/project/source identities not established. No counts invented and no local snapshot substituted. |
| Measured stored/served dimensions, model provenance and compatibility | **UNVERIFIED**: stored vectors/model not reached; no scope invented to run a probe. Probe tooling tested only. |
| Neo4j node/edge/index/vector/provenance coverage and integrity | **UNVERIFIED**: no authorized project identity established; deployed graph scope/topology still needs discovery and a bounded follow-up diagnostic increment. |
| Migration eligibility and non-destructive disposition | **CLOSED**: no live records classified; conservative tooling never authorizes legacy provenance-unknown vectors for copying. Preserve all existing data; recover source/content/model evidence before transfer/re-embedding. |
| Diagnostic tests prove no writes/startup | **PASS (tooling)**: 32 tests, including actual read-only SQLite rejection/hash preservation, forbidden startup imports, full pagination, remote read-only refusal, and Neo4j read-transaction mocks. Live permissions not certified. |
| Inventory reviewed with reviewer/date/scope/decision | **PENDING USER REVIEW**: this is an access-failure artifact, not a complete inventory eligible for approval. No migration or Stage B permitted. |

**Changed/new files and review:** A.1 committed `backend/inventory/{__init__.py,sql.py,report.py,graph.py,README.md}`, `backend/scripts/inventory.py`, `backend/tests/test_inventory.py`, and this checklist in `bc78080`. A.2 adds secret-free access reasons/tests, README evidence and `backend/inventory/reports/2026-10-18-access-blocker.json`; final status/diff/new artifact must be reviewed before its Conventional Commit. No application schema/data/readiness or frontend changes. Frontend checks were not rerun because this increment is standalone backend diagnostics.

**Historical A.2 required next action (resolved by A.3/A.4 except user review):** establish verified read-only SQL access, discover scopes, reach Neo4j/Ollama and complete inventory. Those measurements now succeeded; remaining gate is the user's inventory review. Existing backend launch still performs schema writes and was not used for these diagnostics.

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

Use a project Python environment with `backend/requirements.txt` dependencies installed. Existing application code additionally imports sibling `ai.*`; until Stage B ownership replacement is complete it is not a self-contained backend install. Stage A diagnostics are independently backend-owned. Frontend dependencies are recorded in `web/bun.lock`.

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

# Repository root: scoped backend tests (84 passed in latest Stage B verification)
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

## 13. Historical Audit/Planning Report — Baseline Before Implementation

This report summarizes the documentation task completed on 2026-10-18. Replace/extend with measured implementation results after executing the plan; the unchecked implementation gates above are intentional.

**Latest implementation status is in Section 2.7:** Stage A diagnostic tooling/live measurements are implemented/verified and user inventory review is approved. Stage A is complete; Stage B is eligible for the next run. The items below preserve the original planning baseline and must not be read as the latest live results.

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
