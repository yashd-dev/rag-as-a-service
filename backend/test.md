# Pytest Suite Audit — Recall (RAG-as-a-Service)

Read-only audit of the Python tests that already exist in this repository. No test, source file,
dependency, or configuration was created or modified. The only artifacts of this audit are the
execution of the existing suites and this report.

> Note on naming: the repository does not use the literal name "Recall" anywhere. The SaaS backend
> under audit is the `backend/` Flask application described in `backend/README.md`; the audit scope
> is that application plus its sibling `ai/` package. This is a deduction based on repository
> contents, not a string match.

---

## A. Test Environment

| Item | Value |
|---|---|
| Repository root | `/home/yashd-dev/Documents/Repositories/rag-as-a-service` |
| Git repository | Yes. `git status --porcelain` is clean (no tracked or untracked changes at audit time). |
| Python | 3.13.14 (`.venv/bin/python`, CPython from uv-managed toolchain) |
| Pytest | 9.1.1 (`.venv/bin/python -m pytest --version`) |
| Pytest config | Only `[tool.pytest.ini_options]` in root `pyproject.toml`: `testpaths = ["tests"]`, `pythonpath = ["."]` |
| Other config searched | No `pytest.ini`, `setup.cfg`, `tox.ini`, or `backend/pyproject.toml` exist. No `addopts`. |
| Coverage tooling | **Not installed.** `pytest-cov` and `coverage` are both absent (see Section F). |
| Dependencies | All runtime deps imported successfully in `.venv`: flask, flask_cors, httpx, networkx, neo4j, libsql, pypdf, boto3, cryptography, openai, python-dotenv, pyvis. Nothing was installed. |
| Dev deps | `pyproject.toml` `[dependency-groups].dev = ["pytest>=8.3.0", "ruff>=0.12.5"]` |

Execution limitations discovered:

- `testpaths = ["tests"]` means a bare `pytest` invocation from the repository root collects **only**
  the root `tests/` tree. The `backend/tests/` tree is **not** collected by the configured invocation
  and must be run explicitly (`pytest backend/tests`). Both were run for this audit.
- The root `tests/backend/*` HTTP tests and the root `tests/conftest.py` fixture point at
  `TURSO_DATABASE_URL = "libsql://test-db.turso.io"`. That host does not resolve, so any test that
  performs real database I/O fails with a network error (see Section E). No database was created.
- `LightRAG/` is registered in Git as a submodule (gitlink mode `160000`, commit
  `453dce83d6d0354a06e46c8d4029a0895c4e054b`). Its `LightRAG/tests/` tree is therefore **not tracked
  by this repository** and is a vendored upstream project, not the Recall suite. It was excluded
  from this audit. `pyproject.toml` also excludes `LightRAG*` from packaging.

Test suites that exist in the repository:

| Suite | Location | Tracked | Collected by configured `pytest`? |
|---|---|---|---|
| Root suite (backend HTTP + `ai/` package) | `tests/` | Yes (12 files) | Yes (`testpaths=["tests"]`) |
| Backend app suite | `backend/tests/` | Yes (6 files) | No — needs explicit path |
| Vendored LightRAG upstream suite | `LightRAG/tests/` | No (submodule) | Out of scope |

No untracked or ignored test files were discoverable in the tracked project: `git status` is clean and
`git check-ignore` reports that no project test file is ignored.

---

## B. Test Inventory

### Root suite — `tests/` (35 tests, 12 files)

| File | Tests | Purpose |
|---|---:|---|
| `tests/ai/test_chunker.py` | 4 | Chunker overlap/blank behavior and OCR text cleaning for graph extraction |
| `tests/ai/test_embeddinggemma.py` | 2 | EmbeddingGemma batch POST contract and dimension validation |
| `tests/ai/test_graph.py` | 7 | Entity normalization/id generation, graph JSON parsing, prompt/schema bounds, LLM request payload |
| `tests/ai/test_r2_connector.py` | 1 | R2 connector public URL construction and supported file types |
| `tests/ai/test_rag_service.py` | 1 | RagService grounded-prompt assembly and source list |
| `tests/ai/test_unstructured_client.py` | 2 | Unstructured API job payload and element-to-text joining |
| `tests/backend/test_credentials_data_sources.py` | 4 | Credential secret redaction and data-source key/ingestion rules |
| `tests/backend/test_documents_query.py` | 3 | Document upload scoping, query route logging, conversation creation |
| `tests/backend/test_graph_routes.py` | 2 | Graph status and HTML routes |
| `tests/backend/test_health.py` | 1 | Health endpoint |
| `tests/backend/test_projects.py` | 8 | Project auth, CRUD, org scoping, slug conflict, forced embedding model |

### Backend app suite — `backend/tests/` (84 tests, 6 files)

| File | Tests | Purpose |
|---|---:|---|
| `backend/tests/test_index_state.py` | 8 | Single-writer indexing state machine, generations, idempotent replay, migration rollback |
| `backend/tests/test_ingestion_state.py` | 9 | Upload/Turso-OCR ingestion, readiness capabilities, partial graph failure, Flask factory write-freedom |
| `backend/tests/test_inventory.py` | 37 | Read-only corpus inventory: scoping, redaction, Hrana read-only enforcement, decoders, Neo4j read transactions |
| `backend/tests/test_live_inventory.py` | 22 | Live multi-source inventory, digest/staleness checks, measurement completeness, versioned evidence coherence |
| `backend/tests/test_rag_primitives.py` | 8 | Chunk span coverage, embedding validation, provider POST contract, Neo4j read scoping |
| `backend/tests/conftest.py` | — | `store` fixture: temp SQLite DB + `IndexRepository` + project row |

Configured-invocation totals: **root suite 35 tests**; **backend suite 84 tests**; **119 project tests total** (excluding the vendored LightRAG submodule).

---

## C. Test Case Catalogue

Parametrized tests are listed once with their parametrization named. All assertions below are taken
verbatim from the inspected source. `store`, `client`, `auth_headers`, `app`, `source` are fixtures
defined in the two `conftest.py` files.

### C.1 `tests/ai/test_chunker.py`

| Test | Verifies | Source under test | Type | Setup / input | Execution | Assertions | Expected outcome | Deps | Limitations |
|---|---|---|---|---|---|---|---|---|---|
| `test_chunker_overlaps_words` | Word-level chunking with overlap and chunk indices | `ai.ingestion.chunker.TextChunker` | Unit | `TextChunker(chunk_size=4, overlap=1)`, input `"0 1 2 3 4 5 6 7 8 9"` | Calls `.chunk(text)` | Contents `["0 1 2 3","3 4 5 6","6 7 8 9"]`; indices `[0,1,2]` | Passes only if overlap window is exact | None | Only tiny numeric input; no Unicode/punctuation |
| `test_chunker_returns_empty_for_blank_text` | Blank text yields no chunks | `TextChunker.chunk` | Unit | `"  \n  "` | `.chunk(text)` | `== []` | Empty list | None | Single whitespace case |
| `test_clean_ocr_for_graph_removes_report_noise` | Strips report boilerplate lines | `ai.ingestion.chunker.clean_ocr_for_graph` | Unit | Multi-line SC Reports OCR sample | Calls cleaner | Noise strings absent; judgment/Constitution text present | Boilerplate removed, substance retained | None | Fixed sample; no assertion on remaining noise forms |
| `test_clean_ocr_for_graph_joins_hyphenated_words` | De-hyphenates across line break | `clean_ocr_for_graph` | Unit | `"nationalisa-\n tion of State Carriage"` | Calls cleaner | `"nationalisation" in cleaned` | Hyphen+whitespace collapsed | None | One phrase |

### C.2 `tests/ai/test_embeddinggemma.py`

| Test | Verifies | Source | Type | Setup | Execution | Assertions | Expected outcome | Deps | Limitations |
|---|---|---|---|---|---|---|---|---|---|
| `test_embeddinggemma_sends_batch_to_ollama` | Exact POST URL, payload, timeout, and returned batch | `ai.embeddings.embeddinggemma.EmbeddingGemmaProvider` | Unit (mocked network) | `monkeypatch` of `httpx.post`; provider `("http://ollama.test","embeddinggemma:300m")` | `embed_texts(["first","second"])` | Returns both vectors; recorded request `(url, {model,input}, 60)` equals expected | Correct batch contract | `httpx` mocked | Does not test auth/errors |
| `test_embeddinggemma_rejects_wrong_vector_dimension` | Dimension guard | same | Unit (mocked) | Response `{"embeddings":[[0.25]*10]}` | `embed_texts(["first"])` | `pytest.raises(ValueError, match="unexpected count or dimension")` | Raises on wrong dim | `httpx` mocked | Single wrong-dim case |

### C.3 `tests/ai/test_graph.py`

| Test | Verifies | Source | Type | Setup | Execution | Assertions | Expected outcome | Deps | Limitations |
|---|---|---|---|---|---|---|---|---|---|
| `test_normalize_entity_name` | Name normalization | `ai.graph.extractor.normalize_entity_name` | Unit | `"  'Supreme   Court'  "` | Call | `== "supreme court"` | Trim/case/space normalization | None | One input |
| `test_entity_id_is_stable` | Deterministic ids | `entity_id` | Unit | `("p1","article 21")` twice | Call | Equal ids | Stable hashing | None | No collision test |
| `test_parse_graph_json` | Parses entities/relations | `parse_graph_json` | Unit | JSON string with 1 entity/1 relation | Call | normalized_name `article 21`; relation `interprets` | Parsed correctly | None | Happy path |
| `test_parse_graph_json_accepts_entity_field` | Accepts `entity` key alias | `parse_graph_json` | Unit | `{"entities":[{"entity":...}]}` | Call | `entities[0].name == "Teacher-in-Charge"` | Alias supported | None | Single alias |
| `test_graph_json_stats_counts_discarded_placeholders` | Drops/stats placeholder `...` | `parse_graph_json`, `graph_json_stats` | Unit | Payload with `...` entity and relation | Call both | Parsed lists empty; stats raw 1/1, placeholders 1/1 | Placeholders discarded & counted | None | One placeholder shape |
| `test_graph_extraction_contract_is_compact_and_bounded` | Prompt/schema bounds | `graph_extraction_prompt`, `GRAPH_EXTRACTION_SCHEMA` | Unit | Sample sentence | Call prompt; read schema | Prompt mentions `at most 4 entities and 4 relations`; schema `maxItems==4`, `additionalProperties is False` | Bounded contract | None | Constant-level |
| `test_graph_extraction_sends_compact_json_schema` | LLM POST format/options | `backend.app.services.llm_client.graph_extraction_llm` | Unit (mocked) | `monkeypatch` `httpx.post`; env dict of models/timeouts | `llm.generate(...)` | Payload `format == GRAPH_EXTRACTION_SCHEMA`; options `{temperature:0,num_predict:700,num_ctx:4096}` | Correct request | `httpx` mocked | No response-error path |

### C.4 `tests/ai/test_r2_connector.py`

| Test | Verifies | Source | Type | Setup | Execution | Assertions | Expected outcome | Deps | Limitations |
|---|---|---|---|---|---|---|---|---|---|
| `test_r2_connector_url_and_supported_files` | Public URL join + extension filter | `ai.storage_connectors.r2_connector.R2Connector` | Unit (mocked boto3) | `monkeypatch` `boto3.client`; base `https://cdn.example.com/root` | `object_url`, `is_supported` | URL `.../root/docs/a.pdf`; `.PDF` True; `.png` False | Correct URL/case-insensitive filter | boto3 mocked | No upload/download behavior |

### C.5 `tests/ai/test_rag_service.py`

| Test | Verifies | Source | Type | Setup | Execution | Assertions | Expected outcome | Deps | Limitations |
|---|---|---|---|---|---|---|---|---|---|
| `test_rag_service_builds_grounded_prompt` | Grounded prompt + sources | `ai.rag.service.RagService.answer` | Unit (fake LLM) | `FakeLLM` asserts prompt contains `Question: What?` and `[chunk_1] Context`; chunk `RetrievedChunk("chunk_1","doc_1","Context")` | `answer("What?", [...])` | Result `{"answer":"Answer","sources":["chunk_1"]}` | Prompt assembly + source mapping | None | Single chunk; no multi/empty case |

### C.6 `tests/ai/test_unstructured_client.py`

| Test | Verifies | Source | Type | Setup | Execution | Assertions | Expected outcome | Deps | Limitations |
|---|---|---|---|---|---|---|---|---|---|
| `test_unstructured_request_data_fast_and_vlm` | Job payload subtype per mode | `ai.ingestion.unstructured_client.UnstructuredClient` | Unit | Client `("key","https://example.com/api")` | `request_data("fast"/"vlm")` then `json.loads` | `job_nodes[0].subtype` == `unstructured_api` / `vlm` | Correct subtype | None | No network call asserted |
| `test_elements_to_text_joins_text_only` | Joins only elements with `text` | same | Unit | List with text and non-text elements | `elements_to_text(...)` | `== "One\n\nTwo"` | Skips non-text, double-newline join | None | Single case |

### C.7 `tests/backend/test_credentials_data_sources.py` (Flask test client, real libsql URL)

| Test | Verifies | Source / route | Type | Setup | Execution | Assertions | Expected outcome | Deps | Limitations |
|---|---|---|---|---|---|---|---|---|---|
| `test_create_credential_never_returns_secret` | Secret redaction + hint | `POST/GET /api/credentials`, `routes/credentials.py`, `services/credential_service.py` | Integration/API | `client`, `auth_headers`; api_key `sk-test1234` | POST then GET | 201; `encrypted_api_key` absent; `api_key_hint == "...1234"`; list item lacks `encrypted_api_key` | Secret never serialized | Real database I/O | **Fails: unresolved `libsql://test-db.turso.io`** |
| `test_private_data_source_requires_keys` | Validation before I/O | `POST /api/data-sources` | API/validation | r2 source without keys | POST | 400 | Rejected | None (fails before DB) | Passes without DB |
| `test_public_data_source_allows_missing_keys` | Public source skips keys | `POST /api/data-sources` | Integration/API | `is_public: True` | POST | 201; no `encrypted_access_key_id` | Allowed | Real database I/O | **Fails: network** |
| `test_turso_ocr_source_starts_background_ingestion` | Source creation triggers ingestion with metadata | `POST /api/data-sources`, `start_turso_ocr_ingestion`, `ProjectRepository` | Integration/API | Monkeys `ProjectRepository` and `start_turso_ocr_ingestion`; turso_ocr config w/ batch_size 100, max_documents 250, skip_graph True | POST | 201; `ingestion_status=="pending"`; started once with project; metadata contains the three values | Background ingestion dispatched with config | Real database I/O (project GET faked) | **Fails: network** |

Root fixture `tests/conftest.py::TestConfig` sets `TURSO_DATABASE_URL="libsql://test-db.turso.io"`, `TURSO_AUTH_TOKEN="test-token"`, `BACKEND_INTERNAL_SECRET`, `CREDENTIAL_ENCRYPTION_KEY`. `auth_headers` = internal secret + user/org/role headers.

### C.8 `tests/backend/test_documents_query.py`

| Test | Verifies | Source / route | Type | Setup | Execution | Assertions | Expected outcome | Deps | Limitations |
|---|---|---|---|---|---|---|---|---|---|
| `test_document_upload_skeleton_is_project_scoped` | Upload scoping + cross-org denial | `POST/GET /api/projects/<id>/documents[...]`, `routes/documents.py` | Integration/API | Creates project; other-org headers | POST upload, GET list | 201; `project_id` matches; cross-org GET 404 | Project-scoped access | Real DB | **Fails: network** |
| `test_query_route_logs_run` | Query run id + mode echo | `POST /api/projects/<id>/query`, `routes/query.py` | Integration/API | message + mode `hybrid` | POST | 200; `mode=="hybrid"`; `query_run_id` startswith `qry_` | Logged query run | Real DB | **Fails: network** |
| `test_conversation_create` | Conversation creation | `POST /api/projects/<id>/conversations`, `routes/conversations.py` | Integration/API | title `Research` | POST | 201; `title=="Research"` | Created | Real DB | **Fails: network** |

### C.9 `tests/backend/test_graph_routes.py`

| Test | Verifies | Source / route | Type | Setup | Execution | Assertions | Expected outcome | Deps | Limitations |
|---|---|---|---|---|---|---|---|---|---|
| `test_graph_status_route` | Status passthrough | `GET .../graph/status`, `routes/graph.py`, `FakeGraphStore` | Integration/API | Monkeys `graph_store` to `FakeGraphStore` | GET | 200; `node_count == 2` | Status served | Real DB (project creation) | **Fails: network** |
| `test_graph_html_route` | HTML rendering | `GET .../graph` | Integration/API | Same fake store | GET | 200; body contains `Article 21` | HTML includes node label | Real DB | **Fails: network** |

### C.10 `tests/backend/test_health.py`

| Test | Verifies | Source / route | Type | Setup | Execution | Assertions | Expected outcome | Deps | Limitations |
|---|---|---|---|---|---|---|---|---|---|
| `test_health` | Health payload | `GET /api/health`, `routes/health.py` | API | `client` | GET | 200; body `{"status":"ok"}` | Healthy | None | Passes |

### C.11 `tests/backend/test_projects.py`

| Test | Verifies | Source / route | Type | Setup | Execution | Assertions | Expected outcome | Deps | Limitations |
|---|---|---|---|---|---|---|---|---|---|
| `test_projects_require_internal_secret` | Auth gate | `GET /api/projects` | API/security | Bad `X-Internal-Secret` | GET | 401 | Rejected | None | Passes |
| `test_create_and_list_project` | Create + list + defaults | `POST/GET /api/projects` | Integration/API | name/description | POST, GET | 201; org/user echo; slug `supreme-court-corpus`; provider `huggingface`; model `google/embeddinggemma-300m`; list length 1 | Project persisted | Real DB | **Fails: network** |
| `test_project_access_is_limited_to_organization` | Org isolation | `GET /api/projects/<id>` | Integration/API | Create, then org_2 headers | GET | 404 | Foreign org cannot read | Real DB | **Fails: network** |
| `test_duplicate_project_slug_conflicts` | Unique slug | `POST /api/projects` | Integration/API | Same name twice | POST x2 | 201 then 409 | Conflict | Real DB | **Fails: network** |
| `test_create_project_always_uses_embeddinggemma` | Forced model | `POST /api/projects` | Integration/API | Requests nomic model | POST | 201; model `google/embeddinggemma-300m` | Server overrides | Real DB | **Fails: network** |
| `test_create_project_normalizes_embeddinggemma_short_name` | Short-name normalization | `POST /api/projects` | Integration/API | `embeddinggemma-300m` | POST | 201; model `google/embeddinggemma-300m` | Normalized | Real DB | **Fails: network** |
| `test_create_project_ignores_other_embedding_model_selection` | Unknown model ignored | `POST /api/projects` | Integration/API | `unknown/model` | POST | 201; forced model | Overridden | Real DB | **Fails: network** |
| `test_delete_project` | Delete + 404 after | `DELETE/GET /api/projects/<id>` | Integration/API | Create then delete | DELETE, GET | 204; then 404 | Removed | Real DB | **Fails: network** |

### C.12 `backend/tests/conftest.py` — `store` fixture

Creates `tmp_path/app.db`, calls `backend.app.db.connection.init_db("file:<tmp>", "local")`, inserts one
project row `('p','o','u','Project','p',1,1,'legacy-model')`, and returns
`(IndexRepository({TURSO_DATABASE_URL, TURSO_AUTH_TOKEN}), path, project_dict)`. This makes the backend
suite a **real-SQLite** suite (no network), using `tmp_path` isolation.

### C.13 `backend/tests/test_index_state.py` (real SQLite, `store` fixture)

| Test | Verifies | Source under test | Type | Setup | Execution | Assertions | Expected outcome | Deps | Limitations |
|---|---|---|---|---|---|---|---|---|---|
| `test_repeatable_migration_preserves_legacy_rows_and_backup` | Dry-run is byte-stable; apply makes 0600 backup; migration idempotent; backup overwrite refused | `scripts/migrate.main`, `db.connection.migrate_db` | Integration/DB | Writes `.env`; drops new tables, inserts legacy doc; runs migrate twice | Calls `main`/`migrate_db`; compares files | DB bytes unchanged on dry-run; snapshot mode `0o600`; snapshot projects == live; embedding_model stays `legacy-model`; doc stays; 2nd backup `FileExistsError` | Migration safe/repeatable | SQLite files | Uses real SQLite; legacy schema hand-built |
| `test_replay_same_source_keeps_identity_generation_and_exact_spans` | Idempotent identity + exact char spans + page metadata | `IndexRepository.stage` | Integration/DB | 400x repeated text + metadata pages | `stage` dry-run then twice | Same generation across all three; documents count 1; attempts 1; every chunk content == `text[start:end]` and pages contain `"page": 1` | Deterministic replay + span fidelity | SQLite | One source key |
| `test_legacy_id_adopted_only_once_and_ambiguity_rejected` | Legacy id adoption + ambiguity conflict | `IndexRepository.stage`, `IdentityConflict` | Integration/DB | Insert legacy doc; then duplicate ambiguous docs | `stage` | First returns `document_id=="old"`; subsequent different-source and ambiguous both raise `IdentityConflict` | One-time adoption, ambiguity blocked | SQLite | — |
| `test_generations_preserved_and_recipe_change_invalidates` | Recipe change invalidates generation | `IndexRepository.stage` | Integration/DB | Same source; then add `embedding_model` to recipe | `stage` x3 | 3 distinct generations; documents count 1; generations count 3 | Content change/recipe change re-generates | SQLite | — |
| `test_failure_and_expired_processing_retry_durably` | Failure code persistence + retry of failed/expired work | `IndexRepository.stage`, `IndexRepository.record_failure` | Integration/DB (fault injection) | Monkeypatches `TextChunker.chunk` to raise `RuntimeError("private payload")` | `stage` → failure, retry, force `processing` expired, retry | Failed row `("failed","RuntimeError",1)`; error text not stored; final `("text_ready",3)`; chunks count 1 | Durable retry semantics | SQLite | Monkeypatch target |
| `test_scope_and_live_lease_reject_competing_work` | Cross-org rejection + live lease busy | `stage` | Integration/DB | Foreign org; set future `lease_until` | `stage` | Foreign raises `IdentityConflict`; live lease returns `busy is True`; generations count 1 | Scope + lease guards | SQLite | — |
| `test_migration_failure_rolls_back` | Transaction rollback | `db.connection.db` | Unit/integration (context manager) | Mutates inside `with db(...)` then raises | Raises within context | embedding_model still `legacy-model`; file exists | Rollback on exception | SQLite | Uses internal context manager |
| `test_failed_cli_migration_restores_pre_migration_schema_and_data` | Backup/restore on CLI failure | `scripts/migrate.main`, monkeypatched `migrate_db` | Integration/DB | `migrate_db` raises after creating table + update | `main([...])` | `pytest.raises(RuntimeError, match="simulated")`; rollback table absent; projects match snapshot | Failure restores pre-migration state | SQLite | Monkeypatch |

### C.14 `backend/tests/test_ingestion_state.py` (real SQLite; `source` fixture builds a turso_ocr source DB)

The `source` fixture seeds a second SQLite DB (`ocr.db`) with a `pdfs` table (one real OCR row, one
whitespace-only row) and inserts a `turso_ocr` data_source row with a `SecretBox("test-key")`-encrypted
secret and JSON `prefix` metadata.

| Test | Verifies | Source under test | Type | Setup | Execution | Assertions | Expected outcome | Deps | Limitations |
|---|---|---|---|---|---|---|---|---|---|
| `test_real_source_dry_run_and_replay_after_failed_advanced_cursor` | Dry-run is non-mutating; failure advanced cursor; replay reuses doc id | `TursoOcrIngestionService.run_background_ingestion`, `IndexRepository` | Integration/DB | Real source DB; monkeypatches chunker to raise then restore | Dry-run, failing run, replay, replacement dry-run | Dry-run 1 processed/1 excluded, both DBs byte-identical; failed_count 1 and no "provider secret" in output; cursor `last_source_id=="b"`; replacement uses same `document_id`; documents 1; attempts 2; source DB unchanged; metadata source_uri/source_row correct | Cursor-safe replay | SQLite x2 | Monkeypatch; single source |
| `test_readiness_never_promotes_chunk_only_and_invalidates_corrupt_chunks` | Capability truthfulness, recipe invalidation, corruption detection | `IndexRepository.readiness`, `corpus_readiness` | Integration/DB | Stage doc; change embedding model; corrupt chunk | Calls readiness/pipelines | Initially `text_ready` capabilities `{text:True,vector:False,graph:False}`; corpus count 1; model change → `pending`; corrupt content → `failed`, text capability False; corpus `failed` | No false promotion; corruption caught | SQLite | Corrupts chunk directly |
| `test_legacy_ready_and_interrupted_work_are_not_readiness_evidence` | Legacy `ready` not evidence; interrupted work failed | `readiness`, `corpus_readiness` | Integration/DB | Insert legacy `ready` doc; set generation `processing`, lease 0 | Calls readiness | Legacy → `pending`; staged → `failed`, `failures[0].code=="interrupted"`, text capability True; corpus total 2 | Legacy/interrupted not treated as ready | SQLite | — |
| `test_partial_graph_failure_preserves_text_without_enabling_retrieval` | Partial graph keeps text, blocks retrieval | `readiness`, `corpus_readiness` | Integration/DB | Set state `graph_partial`,`error_code='extraction_failed'` | Calls readiness | State `graph_partial`, `retry_eligible`; capabilities `{text:True,vector:False,graph:False}`; corpus `graph_partial` | Text preserved, no retrieval | SQLite | — |
| `test_source_cli_defaults_to_read_only_preview` | CLI defaults to dry-run, non-mutating | `scripts/index_source.main` | Integration/CLI | Writes env file from config; `capsys` | `main([...])` | Return 0; stdout JSON `dry_run is True`; both DBs byte-identical | Safe preview default | SQLite x2 | — |
| `test_native_pdf_extraction_keeps_page_spans` | PDF page-span metadata | `IngestionService.register_upload`, `ingest_uploaded_file`, `extract_text` | Integration (fake PdfReader) | Monkeypatches `ingestion.PdfReader` with 2 pages | Register, ingest, extract | `capabilities.text is True`; `text[pages[1].start:end] == "Page two."` | Accurate page spans | Monkeypatched PdfReader | Does not use real pypdf parsing |
| `test_extraction_failure_persists_retryable_document_failure` | Unknown type persists failure | `IngestionService` | Integration/DB | Nonexistent `file.unknown` | `ingest_uploaded_file` | `raises(Exception, match="Text staging failed")`; readiness `failed`; generation `failed` | Retryable failure persisted | SQLite | — |
| `test_flask_factory_is_write_free_and_exposes_truthful_status` | App factory writes nothing at construction; upload/status/query semantics | `backend.app.create_app`, `routes/documents`, `routes/query`, `AuthContext` | Integration/API | Config class with tmp upload dir; monkeypatches `auth_or_error` | Build app, upload twice, status, 3 query modes, invalid modes, foreign project, invalid body | DB unchanged on create; uploads 201 `text_ready` no vector; documents 1; status `text_ready`; vector/graph/hybrid → 409; `mode=[]`→400; `["bad"]`→400; foreign →404; JSON list →400 | Truthful, non-destructive factory | Real Flask + SQLite | Monkeypatches auth |
| `test_no_sibling_or_lightrag_runtime_dependencies` | No `ai`/`lightrag` imports in backend or web | AST scan of `backend/**/*.py`, regex scan of `web/**/*.{ts,tsx,js,mjs}`, requirements/package.json | Static/architecture | Walks repo files | Parses imports; scans text | No forbidden imports; no lightrag in requirements or package.json deps | Backend stays standalone | Filesystem only | Regex/static; `web/` may not exist (walk yields nothing) |

### C.15 `backend/tests/test_inventory.py` (read-only inventory; SQLite + mocked drivers)

| Test | Verifies | Source under test | Type | Setup / params | Execution | Assertions (summary) | Deps |
|---|---|---|---|---|---|---|---|
| `test_full_scan_is_scoped_and_never_confuses_labels_with_provenance` | Scoped counts, dimension/classification, redaction, read-only | `inventory.report.application_report`, `inventory.sql.open_reader` | Integration/DB | Fixture DB with mixed vectors incl. foreign org | Report + DELETE attempt | chunk_embeddings count 5; dimensions `{3:2,2:2}`; classification dict; resolved_document 4; stale_count None; no "actual text"; DELETE raises `OperationalError`; file hash unchanged | SQLite |
| `test_missing_schema_is_not_empty_corpus` | Missing schema reported as blocker | `application_report` | Integration/DB | Empty DB file | Report | `tables.documents == {state:"missing_schema"}`; `blockers` non-empty | SQLite |
| `test_native_decoder_failure_is_not_success_or_guessed_blob` | Undecodable vectors block, never guess | `application_report` | Integration/DB | Fixture DB (no `vector_extract`) | Report | `vectors.state=="blocked"`; `"dimensions" not in vectors` | SQLite |
| `test_reader_rejects_write_paths_before_driver` | SQL write/escape rejection pre-driver | `inventory.sql.Reader.query`, `sql.blocked` | Unit/security | Parametrized 7 statements (DELETE, CREATE, PRAGMA off, multi-stmt, load_extension, writefile) | `Reader(NeverExecute()).query(stmt)` | `pytest.raises(ValueError)`; driver never called | None |
| `test_no_accidental_file_creation` | Opening missing DB does not create it | `open_reader` | Integration | Nonexistent path | `open_reader` | `raises(FileNotFoundError)`; file still absent | Filesystem |
| `test_vector_validation` | Vector state/dim decoder | `inventory.report.vector_status` | Unit | Parametrized 8 values (None/[]/bools/NaN/inf/zeros/bad JSON/valid) | Call | Tuple `(state,dimension)` matches each row | None |
| `test_source_mapping_is_discovered_quoted_and_never_emits_text` | Source discovery/quoting/redaction, safe fallback | `source_report`, `identifier` | Integration/DB | Quoted table/columns with private text | Report + identifier | total 3; eligible `{rows:2,nonempty_text:1}`; no private text; unverified mapping → `mapping_not_verified`; identifier escapes quotes | SQLite |
| `test_source_membership_checked_before_decryption` | Project mismatch short-circuits | `inventory.scripts.source_inventory` | Integration/DB | data_sources row mapped to foreign project | Call | `{state:"source_project_mismatch"}` | SQLite |
| `test_standalone_command_imports_no_startup_or_sibling_modules` | CLI import isolation | `scripts/inventory.main` via subprocess with import blocker | Subprocess/architecture | Import guard script | `main(["--help"])` | returncode 0 | Python subprocess |
| `test_report_redacts_driver_exceptions_and_missing_config` | Redaction + gate closed | `build_report` | Unit | Env with token in URL | Build | `application.state=="blocked"`; no token; `gate=="CLOSED"`; `neo4j.state=="blocked"` | None |
| `test_command_does_not_overwrite_prior_evidence` | Evidence immutability | `scripts/inventory.main` | Unit | Existing report file | `main([...])` | `raises(FileExistsError)`; content unchanged | Filesystem |
| `test_neo4j_only_uses_read_transactions` | Read-only Neo4j schema queries | `inventory.graph.graph_report` | Unit (mocked neo4j) | Fake transaction/session/driver; asserts `READ_ACCESS` | `graph_report(...)` | 8 queries, 8 measurements, no password in output | neo4j mocked |
| `test_command_full_run_and_startup_boundary` | Full CLI run/exit code/startup isolation | `scripts/inventory.main` via subprocess | Subprocess/integration | Fixture DB, minimal env | Run module | returncode 2; report documents count 1; vectors blocked; gate CLOSED | SQLite + subprocess |
| `test_all_pages_are_measured_not_only_first_sample` | Pagination beyond first page | `application_report` | Integration/DB | 501 extra rows | Report | count 506; unknown_blocked 502 | SQLite |
| `test_remote_sql_described_before_execute_and_refuses_nonreads` | Hrana describe-before-execute; refuse non-read-only | `inventory.sql.Reader`, `inventory.hrana` | Unit (mocked transport) | Parametrized `readonly` True/False/None | `reader.query("SELECT 1")` | True→result; else `RuntimeError`; request types `["describe", "execute"|"close"]` | httpx MockTransport |
| `test_model_probe_is_transient_and_reports_measured_width` | Probe transient, dimension reported, not persisted | `build_report` | Unit (mocked) | `probe_model=True`; mocked POST | Build | dimension 3; persisted False; revision `unverified`; 1 call; path `/api/embed` | httpx mocked |
| `test_configuration_blockers_are_actionable_without_disclosing_values` | Actionable reasons, no value leak | `build_report` | Unit | Parametrized 3 envs | Build | reason matches; no "private" | None |
| `test_hrana_description_error_or_foreign_origin_never_executes` | Description error/foreign origin blocks execute | `inventory.sql.Reader` | Unit/security | Parametrized 2 payloads | `reader.query("SELECT 1")` | `raises(RuntimeError)`; "execute" never sent | httpx mocked |
| `test_cli_dotenv_precedence_matches_backend_without_startup` | dotenv vs shell precedence | `scripts/inventory.main` | Unit | env file + shell env; monkeypatched `build_report` | `main([...])` | Captured env matches expected precedence; return 2 | None |

### C.16 `backend/tests/test_live_inventory.py`

| Test | Verifies | Source under test | Type | Setup / params | Execution | Assertions (summary) | Deps |
|---|---|---|---|---|---|---|---|
| `test_source_full_scan_fingerprints_exclusions_and_no_text_emission` | Full scan classification, manifest, redaction | `inventory.live.source_inventory` | Integration/DB | `pdfs` table with 4 rows | Call | watermarks_match/counts_reconciled True; classification 1/3; distinct_ids 4; with_page_count 0; manifest 4; probe returns real text (returned, not in report); no text in JSON | SQLite |
| `test_app_empty_vectors_and_historical_source_flags_do_not_imply_readiness` | Empty vectors / stale source flags ≠ readiness | `inventory.live.app_inventory` | Integration/DB | App DB with docs/sources; monkeypatched reader | Call | stored_vectors 0; expected_chunk None; stale_count 0; blockers []; reconciliation counts; integrity counts; no private url | SQLite |
| `test_model_checks_served_digest_and_actual_source_query_widths` | Digest change and dimension mismatch block | `inventory.live.model_inventory` | Unit (mocked) | Parametrized (changed_digest, different_dimensions) | `model_inventory(...)` | state `measured`/`blocked`; persisted 0; probed True; no excerpt leak; 4 requests | httpx mocked |
| `test_graph_empty_denominators_are_not_readiness_and_nonempty_needs_mapping` | Empty DB ≠ ready; nonempty blocked | `inventory.live.graph_inventory` | Unit (mocked neo4j) | Parametrized nodes 0/10 | Call | 9 queries; nodes==0 → `verified_empty_database_not_ready` + `{valid:0,total:0}`; else `blocked` | neo4j mocked |
| `test_service_failure_keeps_other_independent_measurements_and_gate_closed` | Partial failure isolation + gate | `inventory.live.inventory` | Unit | Monkeypatch source to raise, others measured | Call | status `incomplete`; application measured; gate `CLOSED_PENDING_USER_REVIEW`; no secret in output | None |
| `test_versioned_live_evidence_is_coherent_and_does_not_claim_index_readiness` | Coherence of committed evidence | reads `inventory/reports/2026-10-18-live.json`, `live.digest` | Data/regression | Committed JSON | Assert many invariants | status complete; decision pending; gate closed; counts == manifest; sha matches; watermark stable; dims 768; digest stable | Committed artifact |
| `test_completion_rejects_missing_required_measurements` | Defect detection matrix | `live.measurement_issues` | Unit (mutates report) | Parametrized 8 defects (None, orphan_vectors, blockers, unknown_staleness, unknown_generation, unclassified, short_scan, source_changed) | Mutate report then check | `bool(issues) is (defect is not None)` | Committed artifact |
| `test_source_change_during_initial_counts_is_detected` | Watermark change during scan detected | `live.source_inventory` | Unit (mocked) | Fake reader + monkeypatched `source_report`, `scan` | Call | events order `["watermark","counts"]`; watermarks_match/counts_reconciled False | None |
| `test_source_counts_classification_and_selection_share_whitespace_policy` | One whitespace policy across count/select/classify | `live.source_inventory`, `report.source_report`, `live.has_text` | Integration/DB | 6 rows incl. Unicode/control/None whitespace | Scan + selector SQL | selected `["a","d"]`; counts agree; sha list matches; reconciled True | SQLite |
| `test_full_inventory_preserves_safe_access_reasons` | Safe reasons on missing config | `live.inventory` | Unit | Parametrized 2 envs | Call | source reason matches; status incomplete; no host leak | None |
| `test_corrected_live_refresh_matches_approved_material_scope_and_eligibility` | Refreshed evidence matches approved | reads two committed JSON reports | Data/regression | Two artifacts | Compare | status complete; issues []; matching connection ids/keys/digests; selector sha list matches eligible manifest rows | Committed artifacts |

### C.17 `backend/tests/test_rag_primitives.py`

| Test | Verifies | Source under test | Type | Setup / params | Execution | Assertions | Expected outcome | Deps | Limitations |
|---|---|---|---|---|---|---|---|---|---|
| `test_chunk_spans_cover_original_ocr_without_normalization` | Exact span coverage, no normalization | `backend.app.services.rag.TextChunker` | Unit (pure) | Text with leading spaces, repeats, CJK+NUL tail | `.chunk(text)` | `len>1`; each `text[start:end]==content`; all non-space indices covered | Lossless coverage | None | Pure string; single text |
| `test_invalid_embeddings_are_rejected` | Vector validation | `embedding_service.validate_vectors` | Unit | Parametrized 5 vectors (all-zero, 767, NaN, bools, strings) | Call | `raises(ValueError)` each | Invalid vectors rejected | None | — |
| `test_provider_posts_actual_text_and_validates_count` | POST contract + empty count guard | `embedding_service.EmbeddingGemmaProvider`, `validate_vectors` | Unit (mocked) | Monkeypatch `httpx.post` asserting URL/payload/timeout | `embed_query`, `validate_vectors([],1)` | Returns 768; payload exact; empty raises ValueError | Correct provider contract | httpx mocked | — |
| `test_graph_reads_are_scoped_bounded_and_never_write` | Read-mode, scoped params, LIMIT | `graph_store.Neo4jGraphStore` | Unit (fake driver) | Fake driver asserting `default_access_mode=READ` and query starts MATCH + LIMIT | `project_graph`, `project_status` | `{"nodes":[],"edges":[],"bounded":True}`; `graph_ready is False` | Bounded read-only queries | Driver faked | No real Neo4j |

---

## D. Implementation Mapping

| Test group | Feature | Implementation exercised | Layer reached | DB used | Covered behavior | Not covered |
|---|---|---|---|---|---|---|
| `tests/ai/test_chunker.py` | OCR ingestion preprocessing | `ai/ingestion/chunker.py` (`TextChunker`, `clean_ocr_for_graph`) | Direct function calls | None | Word overlap, blank input, boilerplate stripping, hyphen join | Chunk span metadata, unicode policy |
| `tests/ai/test_embeddinggemma.py` | Embeddings | `ai/embeddings/embeddinggemma.py` | Direct (httpx mocked) | None | Batch POST body/url/timeout, dim guard | Auth, retries, error bodies |
| `tests/ai/test_graph.py` | KG extraction | `ai/graph/extractor.py`; `backend/app/services/llm_client.py::graph_extraction_llm`/`GRAPH_EXTRACTION_SCHEMA` | Direct + mocked HTTP | None | Normalization, parsing, placeholder stats, bounded schema, request options | Real model output quality |
| `tests/ai/test_r2_connector.py` | Storage connector | `ai/storage_connectors/r2_connector.py` | Direct (boto3 mocked) | None | URL join, extension filter | Listing, download |
| `tests/ai/test_rag_service.py` | Answer synthesis | `ai/rag/service.py::RagService.answer` | Direct (fake LLM) | None | Grounded prompt, source list | Empty/multi-chunk, citations |
| `tests/ai/test_unstructured_client.py` | Document parsing API | `ai/ingestion/unstructured_client.py` | Direct | None | Job subtype, element join | Actual HTTP submission/response handling |
| `tests/backend/test_health.py` | Health | `backend/app/routes/health.py` | Flask API | Real (network) | 200 ok | — |
| `tests/backend/test_projects.py` | Project management | `routes/projects.py`→`services/project_service.py`→`db/repository.py` | Flask API → service → DB | Real libsql (fails) | Auth gate, CRUD, slug, org scope, forced embedding model | Would pass with a working DB |
| `tests/backend/test_credentials_data_sources.py` | Credentials & data sources | `routes/credentials.py`, `routes/data_sources.py`, `services/credential_service.py`, `services/crypto.py`, `start_turso_ocr_ingestion` | Flask API → service | Real libsql (fails except validation test) | Redaction, key validation, ingestion dispatch | — |
| `tests/backend/test_documents_query.py` | Upload/query/conversations | `routes/documents.py`, `routes/query.py`, `routes/conversations.py` | Flask API → service → DB | Real libsql (fails) | Scoping, run id, conversation create | Retrieval result quality |
| `tests/backend/test_graph_routes.py` | Graph API | `routes/graph.py`, `services/graph_store.py` (faked) | Flask API | Real libsql (fails) | Status passthrough, HTML render | Live Neo4j |
| `backend/tests/test_index_state.py` | Indexing state machine | `db/indexing.py::IndexRepository` (`stage`, `readiness`, `corpus_readiness`, `record_failure`), `db/connection.py::init_db/migrate_db`, `scripts/migrate.py` | Direct service → SQLite | Real SQLite | Idempotency, generations, spans, leases, retries, migration safety | Retrieval, embeddings |
| `backend/tests/test_ingestion_state.py` | Ingestion & readiness | `services/ingestion_service.py` (`IngestionService`, `TursoOcrIngestionService`), `db/indexing.py`, `backend/app/__init__.py::create_app`, `scripts/index_source.py`, `services/crypto.py::SecretBox` | Service + Flask API → SQLite | Real SQLite (2 DBs) | Dry-run safety, cursor replay, capability truthfulness, partial graph, PDF spans, failure persistence, factory side-effect freedom | Real OCR provider, real PDF parsing (PdfReader faked) |
| `backend/tests/test_inventory.py` | Read-only inventory CLI | `inventory/sql.py`, `inventory/report.py`, `inventory/graph.py`, `inventory/hrana.py`, `scripts/inventory.py` | CLI + service → SQLite / mocked remote | Real SQLite + mocks | Scoping, redaction, read-only SQL, Hrana describe-before-execute, vector decoding, Neo4j read tx | Live Turso/Neo4j |
| `backend/tests/test_live_inventory.py` | Live inventory orchestration | `inventory/live.py` (`source_inventory`, `app_inventory`, `graph_inventory`, `model_inventory`, `measurement_issues`, `inventory`, `digest`), `inventory/report.py`, committed reports | Orchestrator → SQLite / mocks | Real SQLite + committed JSON | Per-source measurement, digest/staleness, completeness, evidence coherence | Real external services |
| `backend/tests/test_rag_primitives.py` | RAG primitives | `services/rag.py::TextChunker`, `services/embedding_service.py`, `services/graph_store.py` | Direct | None (mocks) | Span coverage, vector validation, provider POST, bounded read queries | Real Neo4j/embeddings |

Related source that has **no test in either suite** (source-grounded observation): routes `routes/credentials.py`, `routes/data_sources.py`, `routes/projects.py`, `routes/documents.py`, `routes/query.py`, `routes/conversations.py`, `routes/graph.py` are exercised only by the root suite, which currently fails on DB connectivity; the service files `services/auth_context.py`, `services/credential_service.py`, `services/data_source_service.py`, `services/project_service.py`, `services/vector_store.py`, `services/llm_client.py` (except the graph-LLM request shape), `db/repository.py`, and the scripts `scripts/backfill_embeddings.py` have no directly-asserted behavior.

---

## E. Execution Results

Environment used: `.venv/bin/python -m pytest` (Python 3.13.14, pytest 9.1.1). No parameters were
changed; `-p no:cacheprovider` was added only to avoid writing new cache state. No packages installed,
no databases created, no migrations applied to persistent data (the backend suite operates entirely in
`tmp_path`; the root suite attempts a real network connection).

### E.1 Root suite — configured invocation (`testpaths = ["tests"]`)

Command:

```
.venv/bin/python -m pytest -p no:cacheprovider -q
```

Result:

```
35 tests collected
15 failed, 20 passed in 39.14s
```

- Collected: **35**
- Passed: **20** (17 in `tests/ai/*`, plus `tests/backend/test_health.py::test_health`,
  `tests/backend/test_projects.py::test_projects_require_internal_secret`,
  `tests/backend/test_credentials_data_sources.py::test_private_data_source_requires_keys`)
- Failed: **15**
- Skipped: **0**
- Collection errors: **0**
- Duration: 39.14s

Failure classification: **environmental failure, not assertion failure**. Every failure is the same
`libsql` Hrana error raised while opening the configured test DB:

```
database_url = 'libsql://test-db.turso.io', auth_token = 'test-token'
>   conn.execute("PRAGMA foreign_keys = ON")
E   ValueError: Hrana: `api error: `status=404 Not Found, body=Host not found
backend/app/db/connection.py:50: ValueError
```

Failing test names:

```
tests/backend/test_credentials_data_sources.py::test_create_credential_never_returns_secret
tests/backend/test_credentials_data_sources.py::test_public_data_source_allows_missing_keys
tests/backend/test_credentials_data_sources.py::test_turso_ocr_source_starts_background_ingestion
tests/backend/test_documents_query.py::test_document_upload_skeleton_is_project_scoped
tests/backend/test_documents_query.py::test_query_route_logs_run
tests/backend/test_documents_query.py::test_conversation_create
tests/backend/test_graph_routes.py::test_graph_status_route
tests/backend/test_graph_routes.py::test_graph_html_route
tests/backend/test_projects.py::test_create_and_list_project
tests/backend/test_projects.py::test_project_access_is_limited_to_organization
tests/backend/test_projects.py::test_duplicate_project_slug_conflicts
tests/backend/test_projects.py::test_create_project_always_uses_embeddinggemma
tests/backend/test_projects.py::test_create_project_normalizes_embeddinggemma_short_name
tests/backend/test_projects.py::test_create_project_ignores_other_embedding_model_selection
tests/backend/test_projects.py::test_delete_project
```

### E.2 Backend app suite — explicit invocation

Command:

```
.venv/bin/python -m pytest backend/tests -p no:cacheprovider -q
```

Result:

```
84 passed in 1.61s
```

- Collected: **84**
- Passed: **84**
- Failed: **0**
- Skipped: **0**
- Errors: **0**
- Duration: 1.61s

### E.3 Combined project totals

| Metric | Root suite | Backend app suite | Project total |
|---|---:|---:|---:|
| Collected | 35 | 84 | 119 |
| Passed | 20 | 84 | 104 |
| Failed | 15 | 0 | 15 |
| Skipped | 0 | 0 | 0 |
| Collection errors | 0 | 0 | 0 |

Tests not run: the vendored `LightRAG/tests/` submodule suite (untracked by this repository) — not
audited. No project test was deselected or skipped.

---

## F. Coverage and Gaps

**Measured coverage is unavailable.** No coverage tool is installed (`import pytest_cov` and
`import coverage` both raise `ModuleNotFoundError`), there is no `.coveragerc`, and `pyproject.toml`
has no `[tool.coverage]` section, no `--cov` in `addopts`, and no coverage dependency. Installing
`pytest-cov` was out of scope (the audit forbids installing packages), so **no line or branch
coverage percentage was measured**. No coverage figure is inferred from test counts.

`pytest --collect-only` reports exactly `35` and `84` collected tests; those are the only counts
asserted here.

Source files that tests visibly exercise (based on imports/calls, not on measurement):

- `ai/`: `ingestion/chunker.py`, `ingestion/unstructured_client.py`, `embeddings/embeddinggemma.py`,
  `graph/extractor.py`, `storage_connectors/r2_connector.py`, `rag/service.py`
- `backend/app/`: `db/connection.py`, `db/indexing.py`, `routes/health.py`, `routes/projects.py`,
  `routes/credentials.py`, `routes/data_sources.py`, `routes/documents.py`, `routes/query.py`,
  `routes/conversations.py`, `routes/graph.py`, `services/ingestion_service.py`, `services/rag.py`,
  `services/embedding_service.py`, `services/graph_store.py`, `services/crypto.py`,
  `services/llm_client.py` (request shape only), `__init__.py`
- `backend/inventory/`: `sql.py`, `report.py`, `graph.py`, `hrana.py`, `live.py`
- `backend/scripts/`: `migrate.py`, `index_source.py`, `inventory.py`

Apparent untested or insufficiently tested behaviors (deduced from the inspected suite):

1. **All database-backed HTTP routes have no passing test in the current environment.** The root
   suite's 15 DB-dependent tests fail on connectivity, so projects/credentials/data-sources/documents/
   query/conversations/graph behavior is effectively unverified at audit time. The only root API tests
   that pass are validation/auth paths that fail before touching the DB.
2. `services/auth_context.py` (`AuthContext`, `auth_or_error`) has no direct test; both suites must
   monkeypatch it. Its real header-parsing/role logic is unverified.
3. `services/credential_service.py`, `services/data_source_service.py`, `services/project_service.py`,
   `db/repository.py`, and `services/vector_store.py` are reached only transitively and never asserted
   in isolation.
4. `services/llm_client.py` is tested only for the graph-extraction POST payload; other LLM behaviors
   (retries, error handling, other schemas) are untested.
5. `scripts/backfill_embeddings.py` has no test.
6. No test exercises real Neo4j, real Turso, real Ollama, or real R2 — all are faked/mocked except the
   root suite, which only fails on connectivity.
7. Chunking overlap/normalization edge cases beyond the single inputs in `tests/ai/test_chunker.py`
   and `test_rag_primitives.py` are not covered.
8. `test_no_sibling_or_lightrag_runtime_dependencies` scans `web/**` but the check is a no-op if
   `web/` is absent; it is a static guard, not runtime verification.

---

## G. Recommended Candidates for Software Engineering Experiment 10

Two distinct, meaningful, currently-passing tests with concrete assertions. Both are from the backend
app suite, which executed cleanly.

### Candidate 1 — Chunk span coverage

- **Test name:** `test_chunk_spans_cover_original_ocr_without_normalization`
- **File:** `backend/tests/test_rag_primitives.py`
- **Functionality verified:** `TextChunker.chunk` produces chunks whose `start`/`end` character spans
  exactly reproduce the original text (`text[chunk.start:chunk.end] == chunk.content`) with no
  whitespace normalization, and every non-whitespace character is covered.
- **Preconditions / inputs:** No fixtures; a literal string built from `"  Case 123.\n\n"`,
  `"Article 21, protects liberty.\n"` repeated 240 times, and the tail `"尾\x00end"`. `TextChunker()`
  instantiated with defaults.
- **Execution steps:** Call `TextChunker().chunk(text)`.
- **Assertions / expected result:** `len(chunks) > 1`; per chunk `text[chunk.start:chunk.end] ==
  chunk.content`; union of covered ranges includes every index whose character is not whitespace.
- **Execution status from this audit:** **PASSED** (part of `84 passed` in `backend/tests`).
- **Why suitable:** Pure, deterministic, dependency-free; the assertion directly encodes the
  correctness property (lossless span coverage) and is easy to explain and reproduce.

### Candidate 2 — Idempotent source replay with exact spans

- **Test name:** `test_replay_same_source_keeps_identity_generation_and_exact_spans`
- **File:** `backend/tests/test_index_state.py`
- **Functionality verified:** `IndexRepository.stage` is idempotent — replaying the same source record
  keeps the same document identity and generation, stores exactly one document and one generation
  attempt, and every persisted `canonical_chunks` row satisfies
  `content == text[start_char:end_char]` with page metadata preserved.
- **Preconditions / inputs:** `store` fixture (temp SQLite DB initialized via `init_db`, one project row
  `p/o/u` with `embedding_model='legacy-model'`); `text = "Article 21.\n\n" * 400`; `metadata` with a
  `url` and one page spanning `0..len(text)`.
- **Execution steps:** `stage(..., dry_run=True)`, then `stage(...)` twice; query `documents`,
  `index_generations`, `canonical_chunks`.
- **Assertions / expected result:** dry-run leaves DB bytes unchanged; the three generation values are
  equal; `documents` count `1`; `attempts == 1`; each chunk satisfies `content == text[start:end]` and
  its `source_pages` contains `"page": 1`.
- **Execution status from this audit:** **PASSED** (part of `84 passed` in `backend/tests`).
- **Why suitable:** Exercises a real service over a real SQLite database, asserts both an identity/
  idempotency invariant and a data-integrity invariant, and is deterministic.

The suite contains more than two suitable candidates (e.g. `test_flask_factory_is_write_free_and_
exposes_truthful_status`, `test_reader_rejects_write_paths_before_driver`), so the requirement for two
is satisfied without fabricating tests.

---

## Accuracy Notes

- All statuses above are taken from actual pytest runs during this audit (Section E).
- Distinctions marked as "deduced" or "deduction" are inferences from code/config, not measured
  results.
- No test, source file, dependency, or configuration was modified. The backend suite was run with
  filesystem isolation via `tmp_path`; the root suite performed read attempts against a
  non-resolving test host and made no verified persistent changes.
