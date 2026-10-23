# Opt-in citation extractor — bounded integration checkpoint

Implementation commit: `e708d87`. User authorization: **Add opt-in citation
extractor**, preserving the old extractor/default and starting only a bounded batch.

## Implementation verification

- Standard suite: **191 passed, 4 opt-in skipped**.
- All C/D/E and new citation disposable-service opt-ins enabled: **195 passed**.
- Targeted citation suite: **14 passed, 1 service opt-in skipped**.
- Scoped Ruff, Black and `git diff --check`: **PASS**.
- Legacy full-extractor class/profile remain the default and are explicitly tested.
  No `.env` setting/default model was changed. New optional selector:
  `GRAPH_EXTRACTION_STRATEGY` (`full_legal` default, `citation_candidates` opt-in).
- CLI `--strategy`/`--model` overrides are process-local and read-only planning
  makes no model call or settings/database write. Pattern/cue/prompt/schema/model
  provenance identifies a separate graph generation.

Controlled disposable-Neo4j tests cover actual storage, same-citation traversal
beyond one seed, cached reuse without new classifier calls and corrupt-evidence
repair. Their model output/vectors are synthetic test fixtures, not legal-quality
acceptance evidence.

## Actual bounded integration

Report: `stage-d-optin-live-batch-01.json`. Process-local local model
`qwen3:1.7b`, digest
`8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7`;
thinking disabled, 64 output-token cap, context 4096, request timeout 120s.

Before inference, the two selected real chunks' source plans were recomputed and
their verifier budget asserted <=4. Actual results:

| Item | Measured outcome |
|---|---|
| Canonical chunks processed | 2 / 10,417 |
| Planned / actual verifier calls | 2 / 2 |
| Valid case-reference entities | 2 |
| Supported CITES assertions | 1 |
| Verified evidence spans / dangling spans | 3 / 0 |
| Cached chunks replayed / extra model calls | 2 / 0 |
| Remaining pending chunks | 10,415 |
| Partial graph publication | Refused; no graph publication |
| C vector retention/capability | All 10,417 verified; vector=true, graph=false |

The accepted source quotation is **`A.I.R. 1973 S.C. 303, referred to`**, from
`data/pdf/year=1973/english/1974_2_195_198_EN.pdf`, original character span
**4426–4459**. The stored assertion is reference-only; it does not claim that the
source court agreed with/applied/overruled the referenced case.

The model declined the other affirmative reference window. Therefore the earlier
standalone 3/3 result is **not** treated as guaranteed recall or generalized
accuracy. Both source plans remain valid, but only the model-supported assertion
was inserted. Total integration wall time (including complete vector/source
checks and cache replay) was 276.79s; it is not model-generation throughput.

The default application extractor/model settings remain unchanged. No full run,
source/OCR re-ingestion, embedding rewrite, hosted text call or graph activation
was performed.

## Read-only coverage planning

`stage-d-optin-coverage-plan-01.json` scanned the complete current canonical input
without model calls or graph writes:

- **10,417** processable chunks; **0** source-plan failures/overflows.
- **78** citation-bearing chunks in **41** documents for the supported exact pattern.
- **10,339** chunks do not match that pattern.
- **90** literal citation-name instances, **59** normalized case references;
  **4** references are shared across documents through mentions.
- **9** chunks have affirmative eligible windows, requiring **11 planned verifier
  decisions** for a full strategy pass before retries/cache effects.

These are exact AIR/SC-pattern and current English-cue counts, **not coverage of
all legal citations or all graph relationships**. The earlier nine eligible
affirmative groups had no cross-document shared affirmative group; mention-only
references can still supply connections. Actual connected retrieval on the live
corpus remains untested and must not be inferred from this plan.

## Required next gates

Review the narrow citation scope, actual source samples, classifier misses and
format/language coverage before scaling. A full pass, shared-source graph
retrieval review, publication/rollback and real vector/graph/hybrid answer/citation
checks remain in `verification-return.md`. Broader judge/statute/concept NER is
still unresolved. Keep the partial graph unpublished until its actual advertised
scope and all required acceptance evidence are agreed and verified.

## Final state and observed status latency

The final lightweight check confirmed a local model endpoint, unchanged embedding
digest, **10,417 current vectors**, **one C publication**, **zero graph publications**,
and active settings still **full_legal / smollm2:135m**. A single fresh full-readiness
call returned **graph_partial**, text=true/vector=true/graph=false, 333 documents.
It took **80.29 seconds**. An earlier combined check repeated several full proofs
and exceeded its 180-second shell limit; it made no writes and is not counted as
a passing check. Full source/vector proof scans are a known marked ceiling, and
status/query latency must be addressed/verified before high-volume serving.
The disposable verification container was stopped after tests.
