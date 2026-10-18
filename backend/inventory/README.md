# Read-only corpus inventory (Stage A)

From the repository root, using the existing Python environment:

```bash
.venv/bin/python -m backend.scripts.inventory --help

# Full Stage A inventory, with explicit credential-owner-wide scope authorization.
# Includes both the configured model and an actual OCR excerpt probe.
.venv/bin/python -m backend.scripts.inventory --env-file backend/.env \
  --all-configured --output /tmp/opencode/inventory-all-new.json

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
  remote statement is first described by the server using Hrana HTTP `describe`;
  execution is refused unless `is_readonly` is exactly true. This replaces the
  unsupported remote `query_only` guard without permitting unchecked SQL.
  Existing local databases may be explicitly addressed by `file:/...`
  and are opened with SQLite `mode=ro` plus `query_only`. There is no local/remote data sync.
- Source: explicit `--source-id` resolves an existing `data_sources` row in the
  selected organization; its stored mapping must match the selected project.
  `CREDENTIAL_ENCRYPTION_KEY` must match the existing persistent key. Source URL,
  token and mapping come from that row, never UI defaults. Table counts cover the
  entire configured input table and do not establish ownership of every row.
  With `--all-configured`, use the separately supplied `OCR_TURSO_DB` and
  `OCR_TURSO_DB_TOKEN` directly. The `pdfs.path/ocr_text/ocr_status/url` mapping was
  discovered live and compared with `dataset-api/main.py`; it is validated against
  the actual schema on every run. No frontend source creation or decryption key
  is needed for this direct diagnostic. These variables are diagnostic inputs,
  not a change to the runtime ingestion configuration.
- Graph: explicitly set `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`; use a
  **read-only Neo4j account** on the deployment's default database. READ_ACCESS
  is routing, not authorization; server permissions remain necessary. No insecure
  default credentials are supplied. Schema/index information is database-wide;
  graph measurements use candidate `organization_id` / `project_id` properties.
  A schema review must confirm deployed scope mapping before interpreting zero
  matches. `--all-configured` additionally measures unfiltered whole-database
  totals: a verified zero-node/zero-edge database makes provenance and vector
  numerators/denominators 0/0, never 100% or readiness. Nonempty topology-specific
  provenance remains blocked until mapped. No database-name configuration is introduced.
- Optional transient model probe (`--probe-model`): `OLLAMA_BASE_URL` (default
  `http://localhost:11434`), `OLLAMA_EMBEDDING_MODEL` (default `embeddinggemma`).
  Calls `/api/embed` with one fixed probe string and a 30-second timeout; no
  vector is persisted. A measured width is not corpus-wide model compatibility
  or proof of a pinned model revision.
  `--all-configured` also calls `/api/tags` before/after probing and `/api/show`,
  records the resolved model digest, and compares numeric dimensions for a query
  probe and up to 1000 characters from actual OCR text (60-second timeout).
  The OCR excerpt is sent only to the configured model service and only its hash
  is included in the report; no embeddings are stored.

Connection identifiers are hashed. Driver exception messages, decrypted secrets,
source URLs and document text are excluded. Do not publish raw environment files.
Reports contain schema/identity metadata; review before sharing.

Historical access failures have enumerated reasons: `missing_database_url`,
`missing_auth_token`, `unsupported_database_url_scheme`, `connection_failed`,
`query_only_unavailable`, or `query_only_not_confirmed`. They do not include driver
messages. The 2026-10-18 configured access attempt was blocked at read-only
confirmation (`query_only_unavailable`, `ValueError`), before any schema or row
reads. Evidence: `reports/2026-10-18-access-blocker.json`. It does not establish
whether the cause is driver/server pragma support or remote access; no corpus
counts can be inferred from that artifact. The new server-described transport
resolves the client guard incompatibility; it refuses unsupported describe calls,
non-read statements and cross-origin bearer-token forwarding. Protocol reference:
https://github.com/tursodatabase/libsql/blob/main/docs/HRANA_3_SPEC.md

## Coverage and limits

Implemented: schema discovery; scoped application counts; complete legacy vector
scan using native `vector_extract`, finite/nonzero/dimension validation, text and
document-link counts; conservative migration classification; OCR counts from the
stored mapping; graph server/index/constraint discovery, scoped labels/properties,
relationship endpoint scope and duplicate ID groups; optional model dimension probe.
Missing schema and measurement failure are explicit, never reported as empty data.

**Current live result:** `reports/2026-10-18-live.json` and its human-readable
summary `reports/2026-10-18-live.md`. Measurements completed for the configured
stores: 333 usable OCR texts, 97 application documents, no persisted chunk
vectors, empty Neo4j, and matching real 768-dimensional source/query probes with
a stable model digest. No unmeasured nonempty graph topology or persisted vector
provenance is being waived: the inspected retrieval stores are actually empty.
Expected future chunk counts cannot exist until canonical chunking; this is
recorded as not applicable before indexing, not a fabricated coverage result.

The remaining Stage A exit requirement is **user inventory review**, not service
connectivity. Changes to source/model/schema invalidate affected eligibility.
Nonempty graphs or failed measurements on a future run keep measurement status
incomplete; the command never approves migration or starts ingestion.

Legacy valid numeric vectors remain `unknown_blocked`, because project model
labels do not prove model/content provenance. Missing/invalid vectors with text
and a valid document link require re-embedding; missing text/document linkage
requires repair first. Preserve legacy data; recover canonical text/source links
and establish model provenance before any migration. No record is authorized for
copy by this initial tool. Classifications include a reproducible scoped selector
and deterministic rules; counts are not added across overlapping stores.
