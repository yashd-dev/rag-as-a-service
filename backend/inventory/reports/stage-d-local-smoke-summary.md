# Standalone local model output checks

These user-directed temporary checks do **not** change production code/model
configuration, write Neo4j facts, or send judgment text to a hosted model.
They do not close the outstanding D/E acceptance checks.

| Artifact | Temporary setup | Clean synthetic citation | Actual OCR outcome |
|---|---|---|---|
| `stage-d-local-model-smoke-03.json` | Installed GLM Edge 1.5B; native advertised context 2048, output 682 | FAIL: AIR classified Judge, SC Statute; invalid endpoints | FAIL: rewritten text/incorrect types/evidence |
| `stage-d-local-model-smoke-04.json` | Installed Qwen 2.5 3B; explicit schema/example prefix, context 4096/output 1000 | Correct expected Case+CITES JSON | FAIL: party classified Judge and unsupported DECIDED_BY |
| `stage-d-local-model-smoke-05.json` | Same Qwen; temporary chat/system role + caption/bench examples, context 4096/output 900 | Correct expected Case+CITES JSON | Caption and reviewed citation chunk both rejected for invalid evidence |

Raw model output is explicitly **unvalidated** in each artifact. Even valid JSON
or matching source substrings alone do not prove correct entity types/legal claims.
For example, the real-caption output still invents a DECIDED_BY statement supported
by a quote about a Labour Court rejecting a contention. The existing guard rejects it.

The clean example genuinely produced this small output, against a **synthetic**
input rather than the real indexed corpus:

```json
{
  "entities": [{"name": "AIR 1967 SC 1326", "type": "Case"}],
  "relations": [{
    "source": -1,
    "target": 0,
    "relation": "CITES",
    "quote": "This judgment cited AIR 1967 SC 1326."
  }]
}
```

The GLM model's 2048-token advertised context is below the existing production
graph workflow's 4096-token minimum. Its smaller standalone request respected
the native limit and is not a bypass/adoption of that model into the pipeline.

## Next authorized trial

The user explicitly selected **“Yes, trial local 1.7B”** for the official Ollama
`qwen3:1.7b` tag (~1.4 GB download; 57 GB disk free at the check). This authorizes
installation and a bounded standalone output trial, not changing the active
application model or starting full-corpus enrichment. Thinking is disabled for
the bounded trial; record the actual pulled digest and outputs rather than assume
that a newer model passes. No hosted judgment-text trial has been authorized.
