import json

import pytest

from backend.app.db.repository import ProjectCreate, ProjectRepository, SimpleRepository
from backend.app.services.auth_context import AuthContext
from backend.app.services.grounding import GenerationFailure
from backend.app.services.query_service import QueryFailure, QueryService
from backend.app.services.retrieval import RetrievalUnavailable
from backend.tests.test_index_state import query
from backend.tests.test_retrieval import row


@pytest.fixture
def service(store, monkeypatch):
    repository, path, project = store
    config = {
        "TURSO_DATABASE_URL": repository.url,
        "TURSO_AUTH_TOKEN": repository.token,
    }
    service = QueryService(config, project, AuthContext("u", "o", "owner"))
    candidate = {
        "chunk": row("chunk", "Source evidence"),
        "vector_score": 0.8,
        "fusion_score": None,
        "methods": ["vector"],
        "path": [],
    }
    retrieved = {
        "context": [candidate],
        "candidates": [candidate],
        "partition": "vectors",
        "graph_key": None,
        "embedding": {"model": "fixture-only"},
        "diagnostics": {"mode": "vector"},
    }
    monkeypatch.setattr(service.retrieval, "retrieve", lambda *args: retrieved)
    monkeypatch.setattr(service.retrieval, "verify", lambda *args: None)
    monkeypatch.setattr(
        "backend.app.services.query_service.generate_grounded",
        lambda *args: (
            json.dumps(
                {
                    "status": "answered",
                    "answer": "Supported answer [S1]",
                    "used_sources": ["S1"],
                }
            ),
            {"provider": "fixture", "model": "fixture-only", "fallback": False},
        ),
    )
    return service, path, retrieved


def test_answer_distinguishes_candidates_used_sources_and_persists_truthful_outcome(
    service,
):
    engine, path, _ = service
    result = engine.answer("question", "vector")
    assert result["status"] == "answered" and result["generation"]["called"]
    assert result["sources"][0]["citation_id"] == result["used_citation_ids"][0]
    assert result["citation_candidates"][0]["excerpt"] == "Source evidence"
    assert query(path, "SELECT status,answer FROM query_runs") == [
        ("completed", "Supported answer [S1]")
    ]


def test_no_context_abstains_without_calling_a_model(service, monkeypatch):
    engine, path, retrieved = service
    retrieved["context"] = []

    def forbidden(*args):
        pytest.fail("No evidence must not call generation")

    monkeypatch.setattr(
        "backend.app.services.query_service.generate_grounded", forbidden
    )
    result = engine.answer("question", "vector")
    assert (
        result["status"] == "insufficient_evidence"
        and result["generation"]["called"] is False
    )
    assert query(path, "SELECT status FROM query_runs") == [("insufficient_evidence",)]


@pytest.mark.parametrize("code", ["invalid_citations", "generation_unavailable"])
def test_generation_failures_never_persist_success_or_private_errors(
    service, monkeypatch, code
):
    engine, path, _ = service

    def failure(*args):
        if code == "invalid_citations":
            return json.dumps(
                {
                    "status": "answered",
                    "answer": "Unsupported [S9]",
                    "used_sources": ["S9"],
                }
            ), {"provider": "fixture", "model": "fixture-only"}
        raise GenerationFailure(code)

    monkeypatch.setattr("backend.app.services.query_service.generate_grounded", failure)
    with pytest.raises(QueryFailure, match="^" + code + "$") as captured:
        engine.answer("question", "vector")
    assert captured.value.run_id
    assert query(path, "SELECT status,answer FROM query_runs") == [("failed", None)]


def test_model_abstention_is_not_persisted_as_a_completed_answer(service, monkeypatch):
    engine, path, _ = service
    monkeypatch.setattr(
        "backend.app.services.query_service.generate_grounded",
        lambda *args: (
            json.dumps(
                {
                    "status": "insufficient_evidence",
                    "answer": "Unsupported claim",
                    "used_sources": [],
                }
            ),
            {"provider": "fixture", "model": "fixture-only"},
        ),
    )
    result = engine.answer("unanswerable question", "vector")
    assert result["status"] == "insufficient_evidence" and result["sources"] == []
    assert (
        result["generation"]["called"] and "Unsupported claim" not in result["answer"]
    )
    assert query(path, "SELECT status FROM query_runs") == [("insufficient_evidence",)]


def test_changed_index_after_generation_invalidates_the_answer(service, monkeypatch):
    engine, path, _ = service

    def changed(*args):
        assert query(path, "SELECT status FROM query_runs") == [("processing",)]
        raise RetrievalUnavailable("index_generation_changed")

    monkeypatch.setattr(engine.retrieval, "verify", changed)
    with pytest.raises(QueryFailure, match="index_generation_changed") as captured:
        engine.answer("question", "vector")
    assert captured.value.status == 409 and query(
        path, "SELECT status,answer FROM query_runs"
    ) == [("failed", None)]


def test_missing_index_is_not_recorded_as_a_completed_query(service, monkeypatch):
    engine, path, _ = service

    def missing(*args):
        raise RetrievalUnavailable("vector_not_ready")

    monkeypatch.setattr(engine.retrieval, "retrieve", missing)
    with pytest.raises(RetrievalUnavailable):
        engine.answer("question", "vector")
    assert query(path, "SELECT count(*) FROM query_runs") == [(0,)]


@pytest.mark.parametrize("scope", ["other_user", "other_org", "other_project"])
def test_foreign_conversation_rejected_before_retrieval(service, monkeypatch, scope):
    engine, path, _ = service
    config = engine.config
    project_id = engine.project["id"]
    if scope == "other_project":
        project_id = ProjectRepository(
            config["TURSO_DATABASE_URL"], config["TURSO_AUTH_TOKEN"]
        ).create(ProjectCreate("o", "u", "Other", "other"))["id"]
    conversation = SimpleRepository(
        config["TURSO_DATABASE_URL"],
        config["TURSO_AUTH_TOKEN"],
        "conversations",
        "conv",
    ).create(
        {
            "project_id": project_id,
            "organization_id": "foreign" if scope == "other_org" else "o",
            "user_id": "other" if scope == "other_user" else "u",
        }
    )
    monkeypatch.setattr(
        engine.retrieval,
        "retrieve",
        lambda *args: pytest.fail("Foreign conversation must not reach retrieval"),
    )
    with pytest.raises(QueryFailure, match="conversation_not_found"):
        engine.answer("question", "vector", conversation["id"])
    assert query(path, "SELECT count(*) FROM query_runs") == [(0,)]


def test_request_budget_and_conversation_payload_are_checked_at_boundary(service):
    engine, _, _ = service
    with pytest.raises(QueryFailure, match="message_too_long"):
        engine.answer("界" * 400, "vector")
    with pytest.raises(QueryFailure, match="invalid_conversation"):
        engine.answer("question", "vector", [])
    with pytest.raises(QueryFailure, match="invalid_message"):
        engine.answer("\ud800", "vector")
