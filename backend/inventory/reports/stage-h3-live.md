# Stage H.3 — live activation, isolation proof and answer blocker

Date: 2026-10-25. Starting commit: `ae89f39`; worktree clean.

**The configured legal corpus is registered and live access/isolation checks pass.
Full Stage H acceptance remains blocked:** the second real provider query was
rejected with `invalid_citations`. No invalid answer was returned. Serving latency
also remains unresolved. G.1 was not started and H is not marked accepted.

## Pre-write inventory and authority

Canonical scope matches accepted Stage C evidence exactly:

- Organization `z94VqUBs7dCK6PdESE7nYmzlfQXL2rFl`;
  project `proj_c1317127b1c4413596c54b21a633a38f`.
- **333 documents / 10,417 current chunks**, no excluded documents.
- Canonical manifest `5f1c67fdcd058eb06d3a7a9f87fbc593b7963dc41e922550cd1360fd8c115689`.
- Ollama `embeddinggemma:latest`, actual compatibility probe validated finite,
  nonzero **768D** output and the unchanged served digest
  `85462619ee721b466c5927d109d4cb765861907d5417b9109caebc4e614679f1`.
- Existing partition
  `02336a1d1a5a22883559a3cfedd22ecdb3b39247342d3c99178e44a1b99f3032`
  remains published; its vector index is ONLINE. Full publication/integrity
  verification passed for **10,417/10,417 vectors** in **59.61 seconds** including
  canonical reads and the model probe. No document embedding/build/publication
  operation was run.

The first Neo4j probes failed while its existing Docker service was starting.
After startup, the existing named data volume, accepted publication and ONLINE
index were verified; no empty replacement or unrelated old container was used.
The other running Next.js process was confirmed to belong to another repository
and was left alone. No scoped Flask/index worker was running before migration.

Operator activation uses the user's confirmed shared legal scope and the explicit
backed-up commands below. Workspace roles and browser-supplied organization IDs
did not authorize maintenance; the existing operator database credentials did.

## Applied operations

From repository root:

```bash
.venv/bin/python -m backend.scripts.migrate --env-file backend/.env
.venv/bin/python -m backend.scripts.migrate --env-file backend/.env --apply \
  --backup backend/storage/backups/stage-h-before-2026-10-25.db

.venv/bin/python -m backend.scripts.register_shared_corpus --env-file backend/.env \
  --organization-id z94VqUBs7dCK6PdESE7nYmzlfQXL2rFl \
  --project-id proj_c1317127b1c4413596c54b21a633a38f
.venv/bin/python -m backend.scripts.register_shared_corpus --env-file backend/.env \
  --organization-id z94VqUBs7dCK6PdESE7nYmzlfQXL2rFl \
  --project-id proj_c1317127b1c4413596c54b21a633a38f --apply \
  --backup backend/storage/backups/stage-h-registration-before-2026-10-25.db
```

Both operations completed successfully; the distinct backups exist with mode
**0600** and are Git-ignored. These filenames are historical evidence: any future
apply operation must use a new backup path. Schema creation and registration did
not copy/relabel/re-embed source records or modify Neo4j vectors/graph publication.

## Actual authenticated browser and provider attempt

Actual production Next.js at `localhost:13003`, Flask at `127.0.0.1:15003`, actual
Better Auth with two owner sessions in an isolated disposable local auth DB, and
the **configured live application Turso, Neo4j, Ollama and answer-provider path**.
Disposable test workspace IDs were unique and their application records were
subsequently removed. Existing production auth users/sessions were not changed.
There were no model, retrieval or provider mocks, fixture endpoints or alternate
RAG store. No application environment/configuration was changed persistently.

Both workspaces created distinct shared legal references through actual dashboard
Server Actions and opened real shared documents. Upload/remove controls were
absent. The two real vector/provider questions were identical:

> Why did the court spare Ram Narain a return to prison after he had spent years
> on bail?

| Attempt | Actual outcome |
|---|---|
| Workspace A | Answered with `[S1]`, one used source, configured `openai_compatible` generation reporting model `gemini-3.8-flash`, no fallback. Its local-reference source URL resolves to exactly the displayed original canonical text. |
| Workspace B | **503 `invalid_citations`**. UI displayed the safe error; SQL persisted `failed` and null answer under B's own workspace/user/reference. The raw invalid provider answer is not persisted or exposed by the current contract. |

Narrow manual source review for A: the answer identifies the lengthy proceedings,
original 1967 sentence, January 1970 bail and harshness of returning him to prison.
These claims appear in reviewed chunk
`chk_ffd0238ef0ad4b6b0a2fc8924f97bfcd6571ac8f2b0d520add8c523d41280248`,
characters **16785–18481**, content hash
`1f9cab4c2e93d9e124b70e9cbfe0cd17dbdc8fe4f76edd2ff8f98624286a2505`.
This is one source-backed smoke result, not broad Stage E faithfulness acceptance.

The browser measurement includes readiness plus the query action: **250.142s** for
A and **293.475s** for B. A's actual query diagnostics report retrieval
**94,235.94ms**, generation **29,946.87ms**; additional full canonical/publication
checks and network overhead are not hidden inside a claimed generation speed.
The existing expensive serving-time proof remains a G.2 issue. Timeouts were not
extended and the bad answer was not retried until a favorable response appeared.

The main browser script stopped on B's failed acceptance assertion. Independent
source/isolation/detach checks continued through the actual authenticated Flask
HTTP boundary; the browser failure is retained in the result, not waived.

## Independent live access/isolation checks

**41 assertions passed** in the scoped follow-up:

- Both own legal references resolve the exact same verified canonical passage;
  anonymous calls return 401 and another workspace's local reference returns 404.
- Direct multipart upload, document deletion and source attachment return
  `403 shared_corpus_read_only` for both workspace owners before mutating data.
- Both workspaces create private corpora and upload actual small text files,
  reaching canonical text readiness. Own source GET returns the exact private
  marker; foreign document listing/source GET and private-chunk resolution through
  a shared reference return 404. This is not G.1 queued/vector ingestion acceptance.
- A test credential is encrypted in the actual app store and excluded from B's
  credential list. No real provider key is created or exposed by this check.
- Query runs retain their requester workspace/user/reference, with truthful A
  completed/B failed outcomes. A foreign conversation is rejected before retrieval
  or generation. No public query-history listing API is claimed.
- Detaching A leaves B's exact canonical passage accessible; both test references
  and private corpora are then removed. H.1's separate canonical-owner deletion,
  CLI authority and database ingestion guards remain covered by their earlier tests.

## Preservation, cleanup and handoff

After scoped cleanup, **every row of all 13 pre-existing application tables**
compares equal to the private pre-migration snapshot, using deterministic row
digests without printing credentials/source bodies. This includes projects,
documents, source mappings, text generations, canonical chunks, data sources,
credentials, conversations/messages/query runs, and legacy vector/shadow tables.
The canonical manifest and **10,417** current chunks are unchanged. The only
persistent new application state is the additive shared schema and intended
`legal` registration.

Disposable test query/credential/project/source rows and private uploaded files
were removed using only this run's generated workspace/user IDs. Existing user
work and legal originals were untouched. Temporary Next.js/Flask proof servers
and isolated Chromium were stopped; the existing Neo4j service was left running.

Temporary reproducible harnesses/artifacts remain under `/tmp/opencode/`:
`h3-preflight.py`, `h3-vector-proof.py`, `h3-live-server.py`, `h3-browser.mjs`,
`h3-isolation.py`, and `h3-proof/`. They are not installed application features.
The committed JSON is a sanitized summary; local auth cookies, operator secrets,
raw full model output and backups are not committed.

**Remaining gate:** investigate the real provider's invalid-citation failure
without weakening validation, and prove successful two-workspace cited answers.
Retain E's independent source/abstention/failure requirements and G.2's serving
performance work. H is not fully accepted; G.1 is not eligible yet. No runtime code
changed in H.3; prior application tests were not rerun for documentation-only edits.
Live operational assertions and `git diff --check` are this increment's checks.
