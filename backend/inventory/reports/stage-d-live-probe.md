# Stage D — first configured-model probe

**Live D acceptance remains OPEN.** C passed before this probe. No full-corpus
enrichment job or graph publication was started.

Actual report: `stage-d-live-batch-01.json`. Four new attempts against the existing
333-document / 10,417-chunk canonical corpus used configured local
`smollm2:135m`, digest
`9077fe9d2ae1a4a41a868836b56b8163731a8fe16621397028c2c76f838c6907`.
Settings: temperature 0, 700 output tokens, 4096 context, 60-second request timeout.

| Actual outcome | Count |
|---|---:|
| Attempted | 4 |
| Valid accepted extractions | 0 |
| Incomplete JSON / `parse_error` | 2 |
| `invalid_endpoints` | 1 |
| `invalid_evidence` | 1 |
| Remaining pending chunks | 10,413 |
| Accepted entities / assertions / evidence spans | 0 / 0 / 0 |

Both parse failures reached `eval_count=700`, `done_reason=length`. The other
responses completed but failed the actual source/endpoint checks. This measures
failure for this configuration and sample; it does not establish that increasing
the output budget alone resolves the reference/evidence errors.

Failures and attempt state are retained in Neo4j `RAGExtraction`. Invalid facts
were not inserted as valid graph evidence. Partial graph status remains explicit.
After the probe, actual capabilities remain **text=true/vector=true/graph=false**.
No source text, canonical generation or embedding was re-ingested/relabelled.

## Available next trials

Read-only metadata discovery confirmed these already-installed local models:
`embeddinggemma:latest` (embedding model), `smollm2:135m`, `qwen2.5:3b`, and
`hf.co/zai-org/glm-edge-1.5b-chat-gguf:Q4_K_M`. The existing platform credential is
configured and its configured `gemini-3.8-flash` ID is present in the provider's
model list. Availability is not an extraction-quality result; no judgment text
was sent to the platform by that metadata lookup.

The next bounded diagnostic may trial the already-installed larger local model
with enough output budget before selecting/adopting a replacement configuration.
Keep model/recipe generations separate, retain this failed probe, validate exact
source output and do not scale or publish on the strength of model availability.
