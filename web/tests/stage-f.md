# Stage F — frontend implementation and controlled browser acceptance

Date: 2026-10-25. User order: **F first, then D, then E**.

## Implemented

- Playground submits the selected corpus/mode and renders E's actual result instead
  of redirecting/discarding it. Questions survive pending requests/errors. Answers
  retain submitted question, status, actual mode and query-run identity.
- Independent backend text/vector/graph capability flags gate modes. Readiness is
  loaded on selection/manual refresh, with counts, failures and verification time;
  no polling repeats the expensive full integrity scans.
- Inline `[S#]` citations and source cards open an authenticated passage page.
  Canonical text, real page/span metadata, hash and current/historical generation
  are displayed. Missing page numbers are explicit; external URLs permit only
  HTTP(S) without userinfo. No arbitrary source-provided HTML is rendered.
- Used sources remain separate from context candidates. Diagnostics display actual
  retrieval/generation timings, provider/model/fallback, ranking and graph paths.
- Runtime checks reject malformed/foreign responses and inconsistent citations.
  Backend requests remain server-side with session-derived identity/internal secret
  and no-store fetches. Next.js Server Actions retain built-in origin checks.
- Backend request ceiling: 30s ordinarily, 120s for readiness/document listing,
  300s for query. Browser readiness ceiling: 125s. These are bounded waits, not a
  resolution of the previously measured 80.29s backend integrity-scan latency.
- Document/corpus readiness replaces the unconditional Ready badge. Corpus creation
  offers only the supported Gemma baseline; upload/source copy describes actual
  text staging and explicit later indexing. Unsupported mock playground tools,
  code snippets, parameter toggles, reasoning and throughput were removed.
- `.gitignore` previously excluded the entire existing `web/lib/` source directory.
  Exception now exposes it to Git. Existing auth/schema/context/utilities were
  preserved; backend helpers were extended and `rag-contract.ts` added.

## Automated checks

From `web/`:

```bash
bun test tests/rag.test.mjs
bun run lint
bunx --no-install tsc --noEmit --incremental false
bun run build
```

Focused tests cover capability gating, empty corpus, malformed/foreign readiness
and query responses, inline citation consistency, historical passages, ID/text
mismatch, escaped links, unsafe source URLs, trusted identity forwarding, no-store
requests, successful action returns, unavailable-mode diagnostics, provider error
redaction, malformed success, UTF-8 question limits and invalid corpus/document lists.

From repository root:

```bash
.venv/bin/python -m pytest backend/tests/test_query_api.py -q -o addopts='' -p no:cacheprovider
git diff --check
```

Backend E contract regression: **10 passed**. Frontend focused tests: **7 passed,
40 assertions**. Frontend lint/typecheck/build and `git diff --check` passed.

## Authenticated browser evidence

Actual production Next.js at `localhost:13000`, actual Better Auth using a disposable
local auth DB/session/workspace, and actual Flask E endpoints at `127.0.0.1:15001`.
Flask uses `backend/tests/conftest.py:store` and `test_query_api.py:api`: real local
canonical SQL/provenance/source resolution, explicitly controlled retrieval vectors,
graph paths and generation output. Temporary harness/artifacts stayed under
`/tmp/opencode/`; production auth/source/index stores were not modified and no real
model or Neo4j enrichment job ran. There is no fixture mode in application code.

| Browser case | Observed result |
|---|---|
| Empty corpus | `pending`, total 0, all capabilities false, submit disabled |
| Select indexed corpus | Vector available; graph/hybrid options disabled while unpublished |
| Submit vector question | Pending UI, question retained, actual Flask answer/run, one used source and two candidates |
| Click inline citation | New authenticated page shows exact original text, characters 0–40, page 1 and verified hash |
| Graph/hybrid with controlled publication | Actual E mode-specific dispatch; two source links, graph expansion/path and hybrid fusion scores visible |
| Missing source pages | Explicit “Page numbers unavailable”; no invented pages |
| Unanswerable | `insufficient_evidence`, zero cited sources; candidates remain separately inspectable |
| Provider outage | Safe provider error/code, no answer, question retained |
| Withdraw publication after readiness | Query refused with `vector_not_ready`; prior answer replaced by error |
| Malformed readiness | Verification error, modes unavailable, submit disabled; question preserved |
| Document/corpus view | “Vector available” corpus badge; document `vector_ready` and separate text/vector/graph indicators |
| Foreign-project passage | “Source passage not found”; no original passage text rendered |
| Anonymous source request | Redirects to `/auth`, no passage text rendered |
| Responsive layout | Authenticated 390px iframe: viewport 390 / document scroll width 390 |

Browser viewport-emulation/resize tools failed at the protocol layer; same-origin
iframe width was used for the responsive check. Native labeled selects/textarea,
keyboard-operable controls, focus rings and live status/error regions are present;
this is not a full accessibility audit. Console showed expected resource HTTP
errors from negative cases/sidebar prefetches. The first document-page probe hit
HTTP 500 because the minimal backend test Config omitted `CREDENTIAL_ENCRYPTION_KEY`.
After adding a disposable key to the temporary fixture configuration, the unchanged
document page passed against actual source/document endpoints. This was fixture
setup, not a production-code fix. Final rebuilt app's vector answer and submitted
question were rechecked. Temporary proof servers were stopped after verification.

## Remaining acceptance

**Frontend implementation and controlled authenticated wiring are verified.**
Actual Supreme Court model quality, full graph publication/coverage, real per-mode
answers/citation faithfulness and real-corpus response latency remain the D/E gates
in `backend/inventory/reports/verification-return.md`. Repeat the authenticated
production-corpus journey after those gates. Graph visualization/layout and broad
platform changes remain deferred under the spec's scope rules.

Runtime setup uses existing `web/.env` auth DB/Better Auth settings, `BACKEND_URL`,
and matching backend/web `BACKEND_INTERNAL_SECRET`; no new configuration or package
dependency. Start backend from root with `.venv/bin/python -m backend.run`; start
web from `web/` with `bun run dev`, or `bun run build` then `bun run start`.
