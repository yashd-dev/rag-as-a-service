# Stage H.4 — unsafe grounded fallback removed; upstream 503 remains

Date: 2026-10-25. Starting commit `92d01e1`, clean worktree. User requested
continuing diagnosis of the live H.3 `invalid_citations` blocker. This is a bounded
shared-generation fix for H acceptance, not completion of full E or provider I.

## Diagnosis

Traced all scoped callers of `generate_grounded`, `messages_for`, `validate_answer`
and the local fallback helper before editing. H.3 B's invalid raw answer/provider
was deliberately not persisted, so its exact historical cause cannot be proven
retroactively. The following is an actual reproduction of a matching failure
path, not an invented reconstruction of B's discarded response.

Run a **fixed three-call batch** through the real configured generation path,
using the same question and three public legal passages retained from H.3 A.
Labels were exactly `S1`, `S2`, `S3`; neither the evidence, model settings nor
question was changed between attempts. No retrieval/database/index write was
needed for this provider diagnosis.

| Before change | Result |
|---|---|
| 1 — 52.41s | Configured OpenAI-compatible generation, reported model `gemini-3.8-flash`, no fallback; valid `[S1]` answer. |
| 2 — 76.99s | Platform unavailable → automatic local `smollm2:135m` substitution → invalid citations. |
| 3 — 124.74s | Same substitution and invalid output again. |

Both local responses contained:

```json
{
  "status": "answered",
  "answer": "the appellant was acquitted.",
  "used_sources": ["S1", "S2", "D1"]
}
```

`D1` was never an authorized source and there were **no inline citations**. The
answer also misstates the reviewed case's sentencing reasoning. The validator was
correct to reject this output. Adding markers, dropping `D1`, relaxing label
matching or manufacturing an abstention would conceal the failure rather than
ground the answer. Syntax/reference validation alone is not an entailment check;
even a superficially valid citation cannot certify arbitrary model prose.

The executable cause is automatic model substitution after a platform failure:
the user did not select the local answer model, and its legal-answer quality had
not passed acceptance. A generic JSON schema did not prevent invented source IDs
or an unsupported acquittal. This is not a tenant/reference-ID mapping bug.

## Smallest fix

`backend/app/services/llm_client.py:generate_grounded` now uses only the configured
platform path. It does not invoke the local fallback helper:

- Missing platform credentials → `503 generation_not_configured`.
- Provider/transport/configuration failure → `503 generation_unavailable`.
- Successful generation retains actual provider/model metadata with
  `fallback: false` and `fallback_reason: null` for response compatibility.
- Existing 60-second SDK timeout, one SDK retry, 1024 output tokens and client
  closure remain. No timeout increase, new retry/repair loop, fallback option or
  provider/model change.
- `validate_answer` and its strict label/inline checks are unchanged. Normal API
  orchestration still persists failed/null-answer runs and redacts transport data.

Legacy `generate_text_with_fallback` remains separate; it is not used by the
grounded query service. Existing `FALLBACK_LLM_MODEL` is not permission to substitute
a grounded model. The README and environment example clarify this behavior.
Selecting platform Mistral/Gemini or BYOK still belongs to I, not this fix.

## Post-change live verification

The same **fixed three-call batch** with unchanged evidence/model settings returned:

| After change | Result |
|---|---|
| 1 — 6.57s | `generation_unavailable`, no local generation. |
| 2 — 63.10s | `generation_unavailable`, no local generation. |
| 3 — 120.70s | `generation_unavailable`, no local generation. |

A separate, single bounded direct-provider diagnostic classified the underlying
error as **`InternalServerError`, HTTP 503**, after **64.90s**. It omitted response
bodies, endpoint URLs and keys. These are real upstream availability failures;
the fix does not claim to repair the external service. Provider request timing
includes the existing SDK's bounded retry behavior, not a new retry loop.

All outcomes are retained, including the earlier successful platform call and all
failures. There was no retry-until-success selection, forced alternate model or
live two-workspace acceptance claim after this change. A healthy upstream is
required before repeating the real cited-answer gate. H remains open and G.1 has
not started; H.3's legal registration/source-isolation evidence stays intact.

Temporary probe artifacts: `/tmp/opencode/h4-citation-probe.py`,
`h4-before.json`, `h4-after.json`, `h4-provider-status.py` and
`h4-provider-status.json`. Raw probe messages/output are local-only; committed JSON
contains a sanitized summary and the small public-source failure regression.
No app/control-plane/source/index data or persistent environment setting changed.

## Regression checks

Permanent tests cover transport/OpenAI/configuration failures without any fallback
call, missing credentials without any provider request, resource closure/error
redaction, the exact reproduced invalid local payload and the **actual Flask
generation path** returning 503 with a failed/null-answer run for both missing and
unavailable platform configurations. Existing success/abstention/index/isolation
coverage remains passing.

```bash
.venv/bin/python -m pytest backend/tests/test_grounding.py \
  backend/tests/test_query_service.py backend/tests/test_query_api.py \
  backend/tests/test_shared_corpus.py -q -o addopts='' -p no:cacheprovider
# 47 passed.

.venv/bin/python -m pytest backend/tests -q -o addopts='' -p no:cacheprovider
# 205 passed, 4 opt-in integration tests skipped in 3.83s.

.venv/bin/ruff check backend/app/services/llm_client.py \
  backend/tests/test_grounding.py backend/tests/test_query_api.py
# All checks passed.
git diff --check
# Passed.
```

No frontend/runtime contract shape, dependency or environment variable was added;
frontend build/browser acceptance was not repeated against an unavailable provider.
Existing startup commands remain `.venv/bin/python -m backend.run` from root and
`bun run dev` or `bun run build && bun run start` from `web/`.
