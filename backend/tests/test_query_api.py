import json
import sqlite3
from contextlib import contextmanager

import pytest

from backend.app import create_app
from backend.app.db.repository import ProjectCreate, ProjectRepository, SimpleRepository
from backend.app.services.neo4j_vectors import canonical_snapshot
from backend.app.services.rag import fingerprint
from backend.app.services.retrieval import RetrievalService, RetrievalUnavailable
from backend.tests.test_index_state import query


@pytest.fixture
def api(store, monkeypatch):
    repository, path, project = store
    text = "The original judgment contains evidence."
    metadata = {
        "source_uri": "https://example.test/judgment",
        "pages": [{"page": 1, "start": 0, "end": len(text)}],
    }
    repository.stage(project, "source", "a", text, metadata, file_name="case-a")
    repository.stage(
        project,
        "source",
        "b",
        "A connected judgment contains related evidence.",
        file_name="case-b",
    )
    config = {
        "TURSO_DATABASE_URL": repository.url,
        "TURSO_AUTH_TOKEN": repository.token,
    }
    initial = canonical_snapshot(config, project)
    state = {
        "vector_ready": True,
        "graph_ready": True,
        "vector_calls": 0,
        "graph_calls": 0,
        "generation_calls": 0,
    }

    class Config:
        TESTING = True
        TURSO_DATABASE_URL = repository.url
        TURSO_AUTH_TOKEN = repository.token
        BACKEND_INTERNAL_SECRET = "fixture-internal-secret"

    app = create_app(Config)
    headers = {
        "X-Internal-Secret": "fixture-internal-secret",
        "X-User-Id": "u",
        "X-Organization-Id": "o",
    }

    @contextmanager
    def stores(service):
        snapshot = canonical_snapshot(config, service.project)

        class Vectors:
            def __init__(self):
                self.key = fingerprint(snapshot["manifest"])
                self.provenance = {
                    "model": "synthetic-test-only",
                    "revision": "a" * 64,
                    "dimensions": 768,
                }

            def require_publication(self):
                if not state["vector_ready"]:
                    raise ValueError("Unpublished test generation")

            def search(self, provider, message, limit):
                state["vector_calls"] += 1
                return [
                    {"chunk": row, "score": 0.9 - index * 0.1}
                    for index, row in enumerate(snapshot["rows"])
                ]

        yield snapshot, None, Vectors()

    monkeypatch.setattr(RetrievalService, "stores", stores)

    def graph(service, vectors):
        if not state["graph_ready"]:
            raise RetrievalUnavailable("graph_not_ready")

        class Graph:
            key = "graph-" + vectors.key

            def search(self, provider, message):
                state["graph_calls"] += 1
                rows = canonical_snapshot(config, service.project)["rows"]
                return {
                    "graph_added": 1,
                    "results": [
                        {
                            "chunk": rows[0],
                            "score": 0.9,
                            "method": "vector_seed",
                            "path": [],
                        },
                        {
                            "chunk": rows[1],
                            "score": None,
                            "method": "graph_expansion",
                            "path": [
                                {
                                    "from_chunk_id": rows[0]["id"],
                                    "chunk_id": rows[1]["id"],
                                }
                            ],
                        },
                    ],
                }

        return Graph()

    monkeypatch.setattr(RetrievalService, "graph", graph)

    def generate(config, messages):
        state["generation_calls"] += 1
        payload = json.loads(messages[1]["content"])
        labels = (
            ["S1"]
            if payload["question"] == "vector question"
            else [item["id"] for item in payload["evidence"]]
        )
        return json.dumps(
            {
                "status": "answered",
                "answer": "The supplied evidence is available "
                + " ".join("[" + label + "]" for label in labels),
                "used_sources": labels,
            }
        ), {
            "provider": "fixture-only",
            "model": "controlled-response",
            "fallback": False,
        }

    monkeypatch.setattr(
        "backend.app.services.query_service.generate_grounded", generate
    )
    return app, app.test_client(), headers, repository, path, project, initial, state


@pytest.mark.parametrize("mode", ["vector", "graph", "hybrid"])
def test_authenticated_flask_query_dispatch_citations_and_real_sql_source_resolution(
    api, mode
):
    _, client, headers, _, path, _, _, state = api
    response = client.post(
        "/api/projects/p/query",
        headers=headers,
        json={"message": mode + " question", "mode": mode},
    )
    assert (
        response.status_code == 200
        and response.json["mode"] == mode
        and response.json["status"] == "answered"
    )
    assert response.json["retrieval_diagnostics"]["mode"] == mode
    assert bool(state["vector_calls"]) == (mode != "graph") and bool(
        state["graph_calls"]
    ) == (mode != "vector")
    if mode == "vector":
        assert (
            len(response.json["sources"]) == 1
            and len(response.json["citation_candidates"]) == 2
        )
    for citation in response.json["sources"]:
        source = client.get(citation["source_view_url"], headers=headers)
        assert (
            source.status_code == 200 and source.headers["Cache-Control"] == "no-store"
        )
        assert source.json["content"] == citation["excerpt"]
        assert (
            source.json["citation_id"] == citation["citation_id"]
            and source.json["is_current_generation"]
        )
    assert query(path, "SELECT status,retrieval_mode FROM query_runs") == [
        ("completed", mode)
    ]


def test_sources_require_trusted_auth_and_hide_foreign_projects_and_orgs(api):
    app, client, headers, repository, _, _, snapshot, _ = api
    chunk_id = snapshot["rows"][0]["id"]
    url = "/api/projects/p/passages/" + chunk_id
    assert client.get(url).status_code == 401
    assert (
        client.get(url, headers=headers | {"X-Internal-Secret": "wrong"}).status_code
        == 401
    )
    assert (
        client.get(
            url, headers=headers | {"X-Organization-Id": "other-org"}
        ).status_code
        == 404
    )
    other = ProjectRepository(repository.url, repository.token).create(
        ProjectCreate("o", "u", "Other", "other")
    )
    assert (
        client.get(
            f"/api/projects/{other['id']}/passages/{chunk_id}", headers=headers
        ).status_code
        == 404
    )
    app.config["BACKEND_INTERNAL_SECRET"] = ""
    assert client.get(url, headers=headers).status_code == 503
    assert (
        client.post(
            "/api/projects/p/query", headers=headers, json={"message": "question"}
        ).status_code
        == 503
    )


def test_source_gets_are_read_only_and_historical_citations_remain_labeled(api):
    _, client, headers, repository, path, project, snapshot, _ = api
    first = next(row for row in snapshot["rows"] if row["file_name"] == "case-a")
    url = "/api/projects/p/passages/" + first["id"]
    before = path.read_bytes()
    current = client.get(url, headers=headers)
    assert current.status_code == 200 and current.json["pages"][0]["page"] == 1
    assert path.read_bytes() == before
    repository.stage(
        project, "source", "a", "Changed canonical judgment.", file_name="case-a"
    )
    historical = client.get(url, headers=headers)
    assert (
        historical.status_code == 200
        and historical.json["is_current_generation"] is False
    )
    assert historical.json["content"] == first["content"]


def test_corrupt_source_is_not_served_and_unknown_sources_are_not_fabricated(api):
    _, client, headers, _, path, _, snapshot, _ = api
    row = snapshot["rows"][0]
    assert (
        client.get("/api/projects/p/passages/unknown", headers=headers).status_code
        == 404
    )
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE canonical_chunks SET content='private-corrupt-value' WHERE id=?",
            (row["id"],),
        )
    response = client.get("/api/projects/p/passages/" + row["id"], headers=headers)
    assert (
        response.status_code == 503
        and response.json["code"] == "source_integrity_failed"
    )
    assert "private-corrupt-value" not in response.get_data(as_text=True)


def test_unpublished_modes_do_not_generate_answers_or_completed_runs(api):
    _, client, headers, _, path, _, _, state = api
    state["vector_ready"] = False
    blocked = client.post(
        "/api/projects/p/query",
        headers=headers,
        json={"message": "question", "mode": "vector"},
    )
    assert blocked.status_code == 409 and blocked.json["code"] == "vector_not_ready"
    assert state["generation_calls"] == 0 and query(
        path, "SELECT count(*) FROM query_runs"
    ) == [(0,)]
    state.update(vector_ready=True, graph_ready=False)
    for mode in ("graph", "hybrid"):
        response = client.post(
            "/api/projects/p/query",
            headers=headers,
            json={"message": "question", "mode": mode},
        )
        assert (
            response.status_code == 409 and response.json["code"] == "graph_not_ready"
        )
    status = client.get("/api/projects/p/indexing/status", headers=headers)
    assert status.json["capabilities"] == {"text": True, "vector": True, "graph": False}
    assert all(item["retry_eligible"] for item in status.json["documents"])
    assert query(path, "SELECT count(*) FROM query_runs") == [(0,)]


def test_foreign_conversations_and_invalid_payloads_are_rejected_before_generation(api):
    _, client, headers, repository, path, _, _, state = api
    conversation = SimpleRepository(
        repository.url, repository.token, "conversations", "conv"
    ).create({"project_id": "p", "organization_id": "o", "user_id": "someone-else"})
    response = client.post(
        "/api/projects/p/query",
        headers=headers,
        json={"message": "question", "conversation_id": conversation["id"]},
    )
    assert (
        response.status_code == 404
        and response.json["code"] == "conversation_not_found"
    )
    for payload in (
        [],
        {"message": 123},
        {"message": "question", "mode": []},
        {"message": "界" * 400},
    ):
        assert (
            client.post(
                "/api/projects/p/query", headers=headers, json=payload
            ).status_code
            == 400
        )
    assert (
        state["generation_calls"] == state["vector_calls"] == state["graph_calls"] == 0
    )
    assert query(path, "SELECT count(*) FROM query_runs") == [(0,)]


def test_api_index_change_during_generation_never_returns_a_stale_answer(
    api, monkeypatch
):
    _, client, headers, repository, path, project, _, _ = api

    def changed(*args):
        repository.stage(
            project, "source", "a", "New source generation.", file_name="case-a"
        )
        return json.dumps(
            {
                "status": "answered",
                "answer": "Old evidence [S1]",
                "used_sources": ["S1"],
            }
        ), {"provider": "fixture", "model": "fixture-only"}

    monkeypatch.setattr("backend.app.services.query_service.generate_grounded", changed)
    response = client.post(
        "/api/projects/p/query",
        headers=headers,
        json={"message": "question", "mode": "vector"},
    )
    assert (
        response.status_code == 409
        and response.json["code"] == "index_generation_changed"
    )
    assert "Old evidence" not in response.get_data(as_text=True)
    assert query(path, "SELECT status,answer FROM query_runs") == [("failed", None)]


def test_api_invalid_model_citations_return_safe_failure_with_failed_run(
    api, monkeypatch
):
    _, client, headers, _, path, _, _, _ = api
    monkeypatch.setattr(
        "backend.app.services.query_service.generate_grounded",
        lambda *args: (
            json.dumps(
                {
                    "status": "answered",
                    "answer": "Private invalid answer [S99]",
                    "used_sources": ["S99"],
                }
            ),
            {"provider": "fixture", "model": "fixture-only"},
        ),
    )
    response = client.post(
        "/api/projects/p/query",
        headers=headers,
        json={"message": "question", "mode": "vector"},
    )
    assert (
        response.status_code == 503
        and response.json["code"] == "invalid_citations"
        and response.json["query_run_id"]
    )
    assert "Private invalid answer" not in response.get_data(as_text=True)
    assert query(path, "SELECT status,answer FROM query_runs") == [("failed", None)]
