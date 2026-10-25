"""Grounded query orchestration with scoped conversations and truthful run outcomes."""

import time

from backend.app.db.repository import SimpleRepository
from backend.app.services.generation import SelectionError, resolve
from backend.app.services.grounding import (
    ABSTENTION,
    MAX_QUESTION_BYTES,
    GenerationFailure,
    citation,
    messages_for,
    validate_answer,
)
from backend.app.services.llm_client import generate_grounded
from backend.app.services.retrieval import MODES, RetrievalService, RetrievalUnavailable


class QueryFailure(RuntimeError):
    def __init__(self, code, status=503, run_id=None):
        super().__init__(code)
        self.code, self.status, self.run_id = code, status, run_id


class QueryService:
    def __init__(self, config, project, auth, *, retrieval_project=None):
        self.config, self.project, self.auth = config, project, auth
        self.retrieval = RetrievalService(config, retrieval_project or project)
        self.runs = SimpleRepository(
            config["TURSO_DATABASE_URL"],
            config["TURSO_AUTH_TOKEN"],
            "query_runs",
            "query",
        )

    def validate(self, message, mode, conversation_id):
        if self.auth.organization_id != self.project["organization_id"]:
            raise QueryFailure("project_not_found", 404)
        if not isinstance(message, str) or not message.strip():
            raise QueryFailure("message_required", 400)
        try:
            size = len(message.encode("utf-8"))
        except UnicodeError:
            raise QueryFailure("invalid_message", 400) from None
        if size > MAX_QUESTION_BYTES:
            raise QueryFailure("message_too_long", 400)
        if not isinstance(mode, str) or mode not in MODES:
            raise QueryFailure("unsupported_mode", 400)
        if conversation_id is not None:
            if (
                not isinstance(conversation_id, str)
                or not 1 <= len(conversation_id) <= 256
            ):
                raise QueryFailure("invalid_conversation", 400)
            conversation = SimpleRepository(
                self.config["TURSO_DATABASE_URL"],
                self.config["TURSO_AUTH_TOKEN"],
                "conversations",
                "conv",
            ).get(conversation_id, self.auth.organization_id)
            if (
                not conversation
                or conversation["project_id"] != self.project["id"]
                or conversation["user_id"] != self.auth.user_id
            ):
                raise QueryFailure("conversation_not_found", 404)

    def answer(self, message, mode, conversation_id=None, generation_config=None):
        self.validate(message, mode, conversation_id)
        selected = None
        if generation_config is not None:
            try:
                selected = resolve(self.config, self.auth, generation_config)
            except SelectionError as exc:
                raise QueryFailure(exc.code, exc.status) from None
        retrieved = self.retrieval.retrieve(message, mode)
        context = retrieved["context"]
        candidates = [
            citation(self.project, item, "S" + str(index + 1))
            for index, item in enumerate(context)
        ]
        run = self.runs.create(
            {
                "project_id": self.project["id"],
                "organization_id": self.auth.organization_id,
                "conversation_id": conversation_id,
                "user_id": self.auth.user_id,
                "query": message,
                "answer": None,
                "retrieval_mode": mode,
                "status": "processing",
            }
        )
        try:
            generation = {
                "provider": None,
                "model": None,
                "fallback": False,
                "called": False,
            }
            elapsed, used = 0, []
            result = {
                "status": "insufficient_evidence",
                "answer": ABSTENTION,
                "used_sources": [],
            }
            if context:
                started = time.perf_counter()
                raw, generation = generate_grounded(
                    self.config, messages_for(message, context),
                    **({"llm_config": selected} if selected is not None else {}),
                )
                elapsed = round((time.perf_counter() - started) * 1000, 2)
                generation["called"] = True
                try:
                    result = validate_answer(raw, [item["label"] for item in candidates])
                except GenerationFailure as exc:
                    if exc.code != "invalid_generation":
                        raise
                    result = {
                        "status": "insufficient_evidence",
                        "answer": ABSTENTION,
                        "used_sources": [],
                    }
                used = [
                    item
                    for item in candidates
                    if item["label"] in result["used_sources"]
                ]
            self.retrieval.verify(retrieved["partition"], retrieved["graph_key"], mode)
            status = (
                "completed"
                if result["status"] == "answered"
                else "insufficient_evidence"
            )
            if (
                self.runs.update(
                    run["id"],
                    self.auth.organization_id,
                    {"status": status, "answer": result["answer"]},
                )
                is None
            ):
                raise QueryFailure("query_run_missing")
            return {
                "project_id": self.project["id"],
                "query_run_id": run["id"],
                "mode": mode,
                "status": result["status"],
                "answer": result["answer"],
                "sources": used,
                "citation_candidates": candidates,
                "used_citation_ids": [item["citation_id"] for item in used],
                "generation": generation,
                "vector_generation": retrieved["partition"],
                "graph_generation": retrieved["graph_key"],
                "retrieval_diagnostics": retrieved["diagnostics"]
                | {
                    "generation_ms": elapsed,
                    "citation_validation": "known_source_labels_and_inline_markers",
                    "embedding": retrieved["embedding"],
                    "retrieved": [
                        {
                            "chunk_id": item["chunk"]["id"],
                            "document_id": item["chunk"]["document_id"],
                            "vector_score": item["vector_score"],
                            "fusion_score": item["fusion_score"],
                            "methods": item["methods"],
                        }
                        for item in retrieved["candidates"]
                    ],
                },
            }
        except Exception as exc:  # noqa: BLE001
            # Persist failed outcomes and redact provider/DB errors before the HTTP boundary.
            code = (
                exc.code
                if isinstance(
                    exc, (QueryFailure, RetrievalUnavailable, GenerationFailure)
                )
                else "query_failed"
            )
            status = (
                exc.status
                if isinstance(
                    exc, (QueryFailure, RetrievalUnavailable, GenerationFailure)
                )
                else 503
            )
            try:
                self.runs.update(
                    run["id"],
                    self.auth.organization_id,
                    {"status": "failed", "answer": None},
                )
            except Exception:  # noqa: BLE001
                # Failed persistence must never return a completed answer.
                code, status = "query_persistence_failed", 503
            raise QueryFailure(code, status, run["id"]) from None
