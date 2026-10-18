# Read-only corpus inventory (Stage A)

From the repository root, using the existing Python environment:

```bash
.venv/bin/python -m backend.scripts.inventory --help

# Explicit identity-metadata discovery, if org/project/source IDs are not known.
# Output contains IDs, not names, credentials, document text or source cursor data.
.venv/bin/python -m backend.scripts.inventory --env-file backend/.env \
  --discover-scopes --output /tmp/opencode/inventory-scopes.json

.venv/bin/python -m backend.scripts.inventory --env-file backend/.env \
  --organization-id <organization-id> --project-id <project-id> \
  --source-id <source-id> --probe-model \
  --output /tmp/opencode/inventory-report.json

.venv/bin/python -m pytest backend/tests -q -o addopts='' -p no:cacheprovider
```

Use a new output filename for each run; existing reports are never overwritten.
Exit **2** means the inventory/review gate remains closed, including successful
measurement runs. Invalid CLI syntax also exits 2; inspect the report and stderr.
The command cannot certify Stage A or approve migration. Report timestamps and
all emitted queries support reproduction; SQL parameters are the explicit scope
or stored source mapping. Queries are separate reads, **not a stable cross-store
snapshot**. Refresh after concurrent corpus/model/schema changes.

## Configuration and protections

No implicit dotenv loading. `--env-file` is explicit, and process environment wins.
The command imports neither `backend.app` nor any sibling RAG implementation.
It never invokes Flask, schema initialization, ensure functions, ingestion, source
creation, backfill, graph writes or indexing. New local JSON evidence is its only
persistent output. No database fallback is allowed.

- Application: `TURSO_DATABASE_URL` (or `TURSO_CONNECTION_URL`) and
  `TURSO_AUTH_TOKEN`. Prefer deployment-issued **read-only tokens**. Every SQL
  connection sets and verifies `PRAGMA query_only`; unsupported servers fail
  closed. Existing local databases may be explicitly addressed by `file:/...`
  and are opened with SQLite `mode=ro`. There is no local/remote data sync.
- Source: explicit `--source-id` resolves an existing `data_sources` row in the
  selected organization; its stored mapping must match the selected project.
  `CREDENTIAL_ENCRYPTION_KEY` must match the existing persistent key. Source URL,
  token and mapping come from that row, never UI defaults. Table counts cover the
  entire configured input table and do not establish ownership of every row.
- Graph: explicitly set `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`; use a
  **read-only Neo4j account** on the deployment's default database. READ_ACCESS
  is routing, not authorization; server permissions remain necessary. No insecure
  default credentials are supplied. Schema/index information is database-wide;
  graph measurements use candidate `organization_id` / `project_id` properties.
  A schema review must confirm deployed scope mapping before interpreting zero
  matches. No database-name configuration is introduced in this increment.
- Optional transient model probe (`--probe-model`): `OLLAMA_BASE_URL` (default
  `http://localhost:11434`), `OLLAMA_EMBEDDING_MODEL` (default `embeddinggemma`).
  Calls `/api/embed` with one fixed probe string and a 30-second timeout; no
  vector is persisted. A measured width is not corpus-wide model compatibility
  or proof of a pinned model revision.

Connection identifiers are hashed. Driver exception messages, decrypted secrets,
source URLs and document text are excluded. Do not publish raw environment files.
Reports contain schema/identity metadata; review before sharing.

## Coverage and limits

Implemented: schema discovery; scoped application counts; complete legacy vector
scan using native `vector_extract`, finite/nonzero/dimension validation, text and
document-link counts; conservative migration classification; OCR counts from the
stored mapping; graph server/index/constraint discovery, scoped labels/properties,
relationship endpoint scope and duplicate ID groups; optional model dimension probe.
Missing schema and measurement failure are explicit, never reported as empty data.

**Still blocking Stage A:** deployed graph scope/topology mapping and semantic
provenance review; chunk/entity/assertion vector coverage and evidence-link
numerators/denominators; dangling source references; corpus reconciliation and
per-vector content/model/revision/generation/staleness evidence; pinned served
model compatibility; user review. This tool deliberately does not guess graph
labels or provenance properties. Its graph report is discovery evidence for a
subsequent bounded Stage A increment, not a complete inventory certificate.

Legacy valid numeric vectors remain `unknown_blocked`, because project model
labels do not prove model/content provenance. Missing/invalid vectors with text
and a valid document link require re-embedding; missing text/document linkage
requires repair first. Preserve legacy data; recover canonical text/source links
and establish model provenance before any migration. No record is authorized for
copy by this initial tool. Classifications include a reproducible scoped selector
and deterministic rules; counts are not added across overlapping stores.
