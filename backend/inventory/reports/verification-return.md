# Mandatory return-to-verification log — Stages C, D and E

> **Required handoff instruction:** After the background indexing and independent
> implementation work, GO BACK and finish the outstanding tests, live-service
> checks, source reviews and acceptance evidence for **C, D and E**. Passing unit
> tests or completing code does not close a stage. Do not declare these stages
> complete, advance their acceptance gates, or describe the corpus as working
> end-to-end until the unchecked items below have actual recorded evidence.

The user explicitly requested this durable reminder while authorizing independent
Stage E development alongside C's indexing. This supplements `spec.md`; it does
not waive any of its data-preservation, model-provenance or retrieval-quality gates.

## C — Neo4j vectors and semantic retrieval: COMPLETE for the advertised vector scope

- [x] Finish the entire current **10,417-chunk / 333-document** vector generation;
  reconcile expected/valid/missing/failed counts and verify the index is ONLINE.
- [x] Recheck served embedding digest, dimensions, finite vectors, content hashes,
  current canonical manifest, source/document links and project/tenant isolation.
- [x] Repeat the build and demonstrate idempotent reuse of all matching valid
  vectors; record retry/repair outcomes and retained prior generations.
- [x] Run `backend/scripts/evaluate_vectors.py` against the user-approved versioned
  `backend/evaluation/stage-c-v3.json`. Save ranked evidence/scores, vector Recall@k/MRR,
  the required BM25-miss comparison and the unanswerable control. Fix required misses.
- [x] Validate configured publication/withdrawal/rollback behavior and readiness
  invalidation; retain backup/legacy data and record final Stage C evidence.

Evidence: `stage-c-complete.md`, `stage-c-vector-evaluation-v3-01.json` and the
preserved failed v1/v2 reports/review history. The original headnote-only evaluations
are not relabeled as passing. This is a reviewed vector smoke set, not held-out
answer-quality evidence. Reopen affected C checks when corpus/model/index changes.

## D — Actual LLM enrichment and graph retrieval: OPEN

- [ ] After C's gate passes, run a small real-model extraction batch and review
  actual typed entities/assertions against their exact original OCR quotations.
  Model tag availability and controlled test responses do not establish legal accuracy.
- [ ] Resolve unsuitable model/output/context behavior before processing the full
  advertised corpus; record the effective extractor model digest and recipe.
- [ ] Complete extraction coverage and investigate empty, failed, timed-out,
  interrupted and unsupported-language results; retry without losing evidence.
- [ ] Freeze and obtain human review of actual multi-document relationship queries,
  expected passages and graph connections. Record canonical IDs/spans/hashes.
- [ ] Run graph retrieval independently. Demonstrate relevant connected evidence
  beyond semantic seeds, correct provenance, bounded traversal and tenant isolation.
- [ ] Verify configured graph integrity, truthful partial/readiness reporting,
  publication/withdrawal and rollback before recording Stage D acceptance.

## E — Grounded query API and citations: OPEN / implementation in progress

- [ ] Finish and run meaningful isolated tests for mode dispatch, hybrid fusion,
  evidence budgets, provider timeouts/fallback diagnostics, generation validation,
  citations, source resolution and conversation/project/org/user isolation.
- [ ] After C/D pass, run the reviewed actual-source set separately through vector,
  graph and hybrid API modes with the configured real generation provider.
- [ ] Record actual retrieval paths, ranked/context-selected evidence, measured
  scores/timings, effective provider/model/fallback and independent per-mode results.
- [ ] Review every emitted citation and every answer claim for correct judgment,
  exact passage support and available page/span references. Valid citation IDs alone
  do not prove that the answer is faithful to the evidence.
- [ ] Verify actual unanswerable questions abstain, and missing/partial/corrupt/stale
  indexes, provider outages, generation changes and invalid conversations never
  become successful completed answers or leak foreign evidence.
- [ ] Exercise authenticated Flask-to-client query and passage-resolution flows;
  record remaining frontend integration separately rather than assuming a working UI.
- [ ] Fix failing required cases and rerun affected checks; add final C/D/E evidence
  links and explicit acceptance decisions here and in `spec.md` before closing stages.

## Evidence already available — does not close the gates above

- C completion: `backend/inventory/reports/stage-c-complete.md` and the source-reviewed
  `backend/evaluation/stage-c-v3.json`; original fixtures/failures remain preserved.
- D implementation and disposable-Neo4j storage/traversal verification:
  `backend/inventory/reports/stage-d-parallel.md`.
- E isolated/live results: **pending**; populate after checks actually run.

Keep this file in the next handoff. Preserve unchecked items until their own
tests/reviews pass; never convert deferred live checks into an inferred pass.
