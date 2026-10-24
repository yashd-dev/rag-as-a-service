# Stage H.1 — backend shared legal access

Date: 2026-10-25. Scope: backend HTTP access and additive metadata only.
Initial Git worktree was clean. No live database migration, registration, source
write, Neo4j write, provider call or re-embedding was performed. Commit was
subsequently authorized by the user; its hash is recorded in the run handoff.
Stage H remains open for dashboard and live acceptance.

## Scope and schema decision

Reuse `projects` as the requester's workspace-local corpus identity. Add:

- `shared_corpora(id, project_id)`: the single `legal` registration points to an
  existing canonical project; its actual organization is resolved from `projects`.
- `project_corpus_references(project_id, shared_corpus_id)`: local projects point
  to that registration without membership in its owning organization.

Creation inserts the local project and reference in one transaction. Existing
projects remain private by default. Registration is a separate operator action,
not a startup action, workspace role or HTTP endpoint. Its read-only plan checks
the explicit owning organization/project; applying requires a new private backup.
The operator must review which source scope becomes shared before applying.

The additive migration executes complete SQL statements, including triggers,
without `executescript` implicitly committing the caller's migration transaction.
Existing canonical rows/model metadata remain untouched. Foreign keys protect
canonical project deletion and cascade local reference removal. Triggers reject
retargeting, sharing a reference, replacing source data with a reference, and
document insertion/moves into references.

## Acceptance → evidence

| Increment criterion | Result / evidence |
|---|---|
| Same legal source, two independent workspaces | PASS locally: both create a legal reference and retrieve the same canonical chunks; no additional documents/chunks are created. |
| Requester-owned state and citations | PASS locally: conversations and query runs retain each requester organization/user/local project; returned citation URLs and source citation IDs match that local reference. |
| Consistent reads | PASS locally: query, canonical passages, documents, readiness and graph routes resolve the canonical scope. Readiness responses retain local identity and disable mutation/retry controls for shared data. |
| Shared read-only for all workspace roles | PASS locally: JSON/multipart uploads, document deletion and source attachment return 403 for reference owners and the canonical owning workspace's owner. Canonical project deletion is denied. |
| Safe detach | PASS locally: deleting one workspace reference leaves the canonical project/documents/chunks/registration and the other workspace's query access intact. |
| Private isolation | PASS locally: other workspaces and anonymous callers cannot read private project/documents/passages; references cannot resolve private chunks. Another workspace's credentials and conversations remain inaccessible; foreign conversation requests produce no query runs. |
| Trusted identity boundary | PASS locally: missing internal-secret configuration denies project access/deletion instead of accepting identity headers. Existing query/source 503 behavior when unconfigured remains tested. |
| Durable metadata and operator registration | PASS locally: repeatable migration preserves data/registration; registration plan leaves database bytes unchanged; apply retains a private backup; same-target reapplication is a no-op; retargeting is rejected. |
| Worker/CLI protection of references | PASS locally at the database boundary: direct canonical staging into a reference fails without creating documents. Canonical-source maintenance remains operator-only via existing backend credentials; no workspace role grants that authority. No new worker is introduced here. |
| Unpublished graph/hybrid | PASS locally: shared queries retain the existing 409 readiness gate, use local response identity and offer no user retry of shared data. This is not D graph acceptance. |
| Live shared legal activation, real providers and dashboard journey | NOT RUN. No production migration/registration performed. Dashboard controls remain the next H increment. |

New regression suite: `backend/tests/test_shared_corpus.py` (8 tests), using the
existing controlled retrieval fixture with actual local libSQL, canonical chunks,
integrity verification and source resolution. Vector/graph/model boundaries are
controlled test doubles, not new live semantic/generation proof. The older
ingestion HTTP test now uses real trusted headers rather than mocking auth
functions that moved behind the common access decision.

## Checks

```bash
.venv/bin/python -m pytest backend/tests -q -o addopts='' -p no:cacheprovider
# 199 passed, 4 skipped in 4.10s. Skips are existing opt-in integration tests.

.venv/bin/ruff check backend/app/db/connection.py backend/app/db/repository.py \
  backend/app/routes backend/app/services/corpus_access.py \
  backend/app/services/auth_context.py backend/app/services/project_service.py \
  backend/app/services/query_service.py backend/app/services/passages.py \
  backend/scripts/migrate.py backend/scripts/register_shared_corpus.py \
  backend/tests/test_shared_corpus.py backend/tests/test_ingestion_state.py
# All checks passed.

git diff --check
# Passed.
```

The first focused run exposed missing encryption configuration in the new test
fixture; a test-only generated encryption key fixed it. The first full run found
the obsolete auth mocks in the existing ingestion test; replacing them with real
trusted headers restored the original upload/readiness assertions. No checks or
security assertions were bypassed.

## Files and rollout

- New: `app/db/corpus_schema.sql`, `app/services/corpus_access.py`,
  `scripts/register_shared_corpus.py`, `tests/test_shared_corpus.py`, this report.
- Updated: database migration/repository, project/query/document/graph/source/
  conversation routes, trusted auth, project/query services and passage citation
  scope; existing ingestion test, migration plan text, README and root spec.
- Git diff and new source/test/schema files reviewed. No dependency or environment
  variable added. Existing `BACKEND_INTERNAL_SECRET` is now mandatory for all
  forwarded-session routes. Do not expose it to browser code.
- Before backend deployment, run the documented read-only migration plan and
  explicit backed-up migration. Then review actual legal org/project IDs and run
  the registration plan; applying registration is a separate operator action.
- Exact migration/registration/Flask commands: `backend/README.md`, sections
  “Run from the repository root” and “Shared legal corpus — Stage H.1 backend
  access”. No CLI command is required for workspace users to create a reference.

Next eligible work is H dashboard creation/read-only integration, followed by
live two-workspace acceptance against the verified legal scope. G.1, I, J and
F.2 implementation have not been started in this run.
