# Stage A audit fixes — verified live refresh

**Window:** 2026-10-18 09:31:37–09:31:58 UTC.
**New evidence:** [`2026-10-18-audit-fixes.json`](2026-10-18-audit-fixes.json).
**Approved baseline:** [`2026-10-18-live.md`](2026-10-18-live.md) and its frozen JSON.

All six audit findings are fixed. The corrected live command returned
`measurement_status: complete`, `measurement_issues: []`,
`source.counts_reconciled: true` and matching pre-count/post-scan watermarks.
No startup, database writes, ingestion, re-OCR or persistent embeddings occurred.

| Finding | Correction | Verification |
|---|---|---|
| 1. False completion with unscanned/unknown vectors | Global/scoped/scanned/classified counts reconcile; project blockers and unknown required coverage prevent completion | Regression cases plus live total/scoped vectors = 0 |
| 2. Diagnostic and backend select different settings | Explicit dotenv defined values override shell values, matching backend Config | Actual CLI test with conflicting URL/token/model and null dotenv fallback; same live connection fingerprints |
| 3. SQL/Python disagree on blank OCR | Shared Python string/`strip()` rule; candidate SQL requires its published Python post-filter, with eligible ID hashes | Scoped/full counts, selectors and classification agree for spaces/newlines/tabs/Unicode/NUL fixtures; live 333 eligible IDs |
| 4. Source watermark starts too late | Capture before initial counts; validate scan/count/status/ID reconciliation | Regression catches an intervening deletion; live counts reconcile |
| 5. Failure reasons disappear | Scoped/full paths share the existing secret-safe exception formatter | Missing OCR URL and missing token produce distinct reasons; arbitrary error messages remain redacted |
| 6. Unused read counter | Deleted both unused writes | Existing server-description/refusal/cleanup tests pass |

## Material comparison with the user-approved inventory

The versioned regression check compares the actual new JSON with the approved
snapshot, not a manually reconstructed expected count:

- Same four redacted connection identifiers and source/application schemas.
- Same **876** source records, **333** usable OCR texts, **543** exclusions.
- Identical source/content manifest and fingerprint:
  `f2c815e1823d011ae1993564cf2402a402ac82d7e74852d2cb31019418081525`.
- Same **3 projects, 97 documents, 14 source configurations**, document records,
  candidate source links and historical invalid mappings.
- **0 application chunk vectors**, **0 Neo4j nodes/edges/vector indexes**.
- Same real **768-dimensional** query/source probes and stable model digest
  `85462619ee721b466c5927d109d4cb765861907d5417b9109caebc4e614679f1`.

Thus the existing user review of the material scope/disposition still applies;
no new approval is inferred for changed data. Both machine reports retain their
original pending-review diagnostic fields. The dated review in the original
readable report remains the authority; the tool never fabricates user approval.

## Reproduce

```bash
.venv/bin/python -m backend.scripts.inventory --env-file backend/.env \
  --all-configured --output /tmp/opencode/inventory-audit-refresh-new.json
.venv/bin/python -m pytest backend -q -o addopts='' -p no:cacheprovider
.venv/bin/ruff check backend/inventory backend/scripts/inventory.py backend/tests --no-cache
```

Use a new output path. Exit 2 retains the diagnostic's closed review gate;
inspect `measurement_status` and `measurement_issues` to distinguish a complete
measurement from a failed one. Source selection now requires the JSON selector's
Python post-filter, not SQL `trim()` alone.

Independent read passes are not a database snapshot. Changes that preserve
counts/timestamps may escape those counters; a migration under concurrent writes
needs a read snapshot or refreshed affected evidence before its writes. This
refresh also matches the entire approved content manifest. No Stage B work was
started; existing data and untracked `backend/docker-compose.yml` are preserved.
