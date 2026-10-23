# Stage E — implemented query API; live answer acceptance remains OPEN

The implementation is present in `3834573`, `7f52f1e` and the user's formatting/API
commit `dd25c62`. This checkpoint verifies that code without overwriting the
formatting work. Stage C is now complete/published; actual Stage D graph quality
and Stage E grounded-answer quality remain separately gated.

## Implemented contract

- `POST /api/projects/<project_id>/query`: real vector/graph/hybrid dispatch,
  reciprocal-rank hybrid fusion, whole-passage/connected-path context budgets,
  bounded generation and explicit insufficient-evidence responses.
- Required trusted forwarded context: configured `BACKEND_INTERNAL_SECRET`,
  matching `X-Internal-Secret`, `X-User-Id` and `X-Organization-Id`. Query/passage
  routes return 503 when trusted backend authentication is unconfigured.
- Query JSON: `message` (nonempty, <=1024 UTF-8 bytes), optional `mode`
  (`vector`/`graph`/`hybrid`, otherwise project default), optional `conversation_id`.
  Conversation project/org/user are checked before retrieval.
- Response preserves `answer`, `project_id`, `query_run_id`, `mode`, and adds precise
  status, cited `sources`, distinct `citation_candidates`, stable `used_citation_ids`,
  actual generation provider/model/fallback, current vector/graph generation and
  measured retrieval/generation diagnostics.
- Model context uses short `[S1]` source labels mapped to stable canonical citation
  IDs. Unknown/missing/inconsistent labels fail closed. References are validated;
  this does **not** independently verify the truth of every generated claim.
- Query runs use `processing` → `completed` only for a validated answered result;
  abstention is `insufficient_evidence`, errors/stale generations are `failed` with
  no answer. Missing indexes never become successful query runs.
- `GET /api/projects/<project_id>/passages/<chunk_id>`: authenticated exact canonical
  text, ID/hash/span/page integrity, source references and current/historical flag.
  Historical references retain original text and are explicitly labeled. Missing
  foreign-project/org sources return 404; corrupt text returns a safe 503.
- Query/passage responses use `Cache-Control: no-store`. Source URL userinfo/unsafe
  schemes are excluded; the authorized internal passage link remains available.
- Existing document/status GETs expose actual published vector/graph capabilities;
  no GET migrates schema, indexes source data or invokes text generation.

Provider configuration remains platform OpenAI-compatible generation, with the
existing Ollama fallback and explicit fallback reason. SDK requests are bounded
at 60 seconds/one retry/1024 output tokens; fallback at 60 seconds/1024 output
tokens. Selected evidence budget is 5000 serialized UTF-8 bytes; full prompt is
limited to 7000 bytes. BYOK, message history, streaming and frontend wiring retain
their separate scopes.

## Verification actually run

1. Current formatted-code standard backend suite: **177 passed, 3 opt-in skipped**.
2. Reused the owned resource-bounded disposable Neo4j 5.26 instance at port 17689
   and enabled all C/D/E opt-in scenarios: **180 passed, 0 skipped**.

```bash
STAGE_C_TEST_NEO4J_URI=bolt://127.0.0.1:17689 \
STAGE_C_TEST_NEO4J_PASSWORD=<disposable-password> \
STAGE_D_TEST_NEO4J_URI=bolt://127.0.0.1:17689 \
STAGE_D_TEST_NEO4J_PASSWORD=<disposable-password> \
STAGE_E_TEST_NEO4J_URI=bolt://127.0.0.1:17689 \
STAGE_E_TEST_NEO4J_PASSWORD=<disposable-password> \
  .venv/bin/python -m pytest backend -q -o addopts='' -p no:cacheprovider
```

The C scenario uses actual Ollama embeddings on test text. The D/E scenarios use
controlled test-only model output/vectors to verify actual Neo4j storage/traversal,
all three Flask modes, graph contribution beyond vector seeds, local SQL query-run
outcomes, exact authorized passage resolution and graph withdrawal refusal.
**They are not live-corpus extraction or generated-answer accuracy evidence.**

The suite includes forged/missing auth, foreign projects/orgs/users/conversations,
invalid inputs, corrupt/historical source text, unpublished modes, no-context/model
abstention, bad citations, provider fallback/secret redaction and index changes
during generation. Scoped Ruff, relevant Black and `git diff --check` passed.

Configured read-only API smoke before C publication also passed: authorized source
GET **200**, exact content hash verified, no-store response; vector query
**409/vector_not_ready**, **zero generation calls**, query-run count **0 → 0**.
An earlier attempt was blocked by transient DNS resolution before database reads;
the later attempt completed successfully without changing credentials or source data.

## Required return to live verification

Keep `verification-return.md` in the handoff. After actual D enrichment/review,
run actual-source vector/graph/hybrid queries using the real generation provider,
review every claim/citation, verify unanswerable abstention and outages, and record
independent per-mode outcomes. Real provider/corpus quality is still unverified;
passing all 180 isolated/service-fixture tests does not close that acceptance gate.

No new application dependency/environment variable was introduced by E. Launch
remains `.venv/bin/python -m backend.run` from repository root. No frontend changes
or working browser playground are claimed.
