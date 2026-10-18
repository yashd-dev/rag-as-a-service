# Backend — Stage B

Stage B owns canonical text, identity and processing state. It does **not** claim
the corpus is indexed: Neo4j vectors, grounded graph retrieval and answer dispatch
are the next stages. Current query modes return **409** with readiness details.

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
the served digest/dimensions still need Stage C publication checks. Existing
`NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD` support read-only graph views.
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
