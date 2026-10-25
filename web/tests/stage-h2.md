# Stage H.2 — dashboard shared legal/private access

Date: 2026-10-25. H.1 committed first as `d7a4797` at the user's request.
This increment completes dashboard wiring and controlled browser proof, not the
live migration/registration or full Stage H acceptance.

## Implemented

- Corpus creation offers **Use existing legal corpus** and **Upload my own data**,
  including from the empty screen. The source choice reaches the authenticated
  backend action; legal creation hides private source/embedding configuration.
- Invalid source selection, a partial Turso credential pair or attempted source
  attachment to legal data is rejected before creating a project. The backend's
  unregistered-legal response becomes a clear, retryable creation error.
- Name/key/description and selected source survive failed actions. Source radios
  sit outside the form's native post-action reset; a controlled hidden value is
  submitted. The document client remounts when project IDs change so successful
  creation/detachment returns to the updated list, while ordinary document
  refreshes preserve selected-corpus state.
- Legal/private labels are visible in corpus listings and playground selection.
  Legal detail explains read-only ownership and links to the playground. Upload
  and document-remove controls are absent for shared sources, including owners.
- Backend project metadata includes `is_shared_reference`: local references show
  **Detach**, with source-preservation copy; the canonical shared project shows
  **Platform-managed**, without a delete form. The existing backend authorization
  remains authoritative for direct HTTP attempts.
- Runtime project-list checks fail closed for missing, incorrectly typed or
  contradictory access metadata. Matching frontend/backend rollout is required.
- A failed document fetch shows unknown/unavailable count in the corpus list and
  detail; it no longer renders `0 documents` or the empty-corpus message. A genuine
  empty successful response still shows the empty state.

## Automated checks

From `web/`:

```bash
bun test tests/rag.test.mjs
# 11 passed, 62 assertions.
bun run lint
bunx --no-install tsc --noEmit --incremental false
bun run build
# All passed; Next.js production build completed.
```

From the repository root:

```bash
.venv/bin/python -m pytest backend/tests/test_shared_corpus.py -q -o addopts='' -p no:cacheprovider
# 8 passed.
.venv/bin/ruff check backend/app/services/corpus_access.py backend/tests/test_shared_corpus.py
# All checks passed.
git diff --check
# Passed.
```

Permanent frontend regressions cover access-metadata failures, legal action
selection/no attachment, availability errors, validation before partial creation
and actual React-rendered unknown counts/detach/canonical protection. Prior F.1
contract/action/citation tests remain passing. Backend tests additionally assert
that reference and canonical metadata differ without changing mutation denial.

## Actual authenticated browser checks

Production Next.js at `localhost:13002`, actual Better Auth with two disposable
local owner sessions/workspaces, actual Flask at `127.0.0.1:15002`, and real local
libSQL/canonical text/source integrity. Model/vector/graph boundaries reuse the
explicit controlled fixture in `backend/tests/test_query_api.py`; they are not
real-provider or live Neo4j proof. Shared registration, files and query state in
this exercise are confined to disposable `/tmp/opencode/h2-proof-5/` stores.

Chrome DevTools MCP was unavailable because its browser profile was already in
use. An isolated headless Chromium profile and raw CDP over Bun's built-in
WebSocket provided real browser interaction without installing a dependency or
changing the application. Temporary harnesses are `/tmp/opencode/h2-fixture.py`
and `/tmp/opencode/h2-browser.mjs`; no test-control endpoint exists in app code.

| Case | Observed result |
|---|---|
| Unregistered legal creation | Clear unavailable alert; no private source form; name/key/source retained for retry. |
| Register disposable canonical scope, retry | Creates a legal reference with shared/read-only labels and Detach, not an empty private project. |
| Owner opens legal detail | Actual canonical documents visible; no upload input or document-remove button. |
| Second owner workspace | Separate reference; first workspace's corpus is absent from its list. |
| Shared query/citation | Actual Flask run, one cited source, local-reference URL and exact original canonical passage. |
| Private creation/upload | Private upload input retained; actual text file staged and listed; removal control present. This does not prove queued/vector ingestion. |
| Populated-corpus document fetch outage | List shows unknown count; detail shows unavailable alert without zero/empty-corpus claims. |
| Detach first reference | First reference disappears; source documents remain and the second workspace still answers from them. |
| Anonymous actual citation navigation | Redirects to the magic-link auth page; no source passage text disclosed. |
| 390px playground | Document scroll width does not exceed viewport width. |

Browser debugging exposed two real post-action reset issues: required text inputs
were cleared after an error, then reset source radios caused a retry to fall back
to private creation. Controlled text inputs plus an out-of-form source selector
and controlled hidden source value fixed both. A project-ID key handles the
same-route success refresh. The final main run passed creation/read/query/upload/
outage/detach cases; a follow-up passed anonymous citation and mobile layout after
correcting the harness's expected auth-page text. Other harness-only corrections
were a corpus-button text selector and JavaScript quoting in the citation selector.
No assertions were waived; all documented cases were completed successfully.

Temporary web/Flask proof servers and the isolated Chromium process were stopped.
No production credentials, source/index records or auth sessions were changed.

## Remaining Stage H gate

At the H.2 handoff, live migration/registration remained unapplied. Subsequent H.3
activation and real-store isolation evidence are in
`backend/inventory/reports/stage-h3-live.md`: migration/registration and isolation
passed; the second real provider query was rejected with `invalid_citations`.
H is still open; G.1 has not started.

No dependencies or environment variables added. Existing `BACKEND_URL`, matching
`BACKEND_INTERNAL_SECRET` and auth/database settings are required. Run Flask from
the repository root with `.venv/bin/python -m backend.run`; from `web/`, use
`bun run dev` or `bun run build` followed by `bun run start`.
