import copy
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from backend.app.services.rag import fingerprint
from backend.app.services.retrieval import (
    RetrievalService,
    RetrievalUnavailable,
    rank_candidates,
    select_context,
)


def row(chunk_id, text):
    return {
        "id": chunk_id,
        "document_id": "doc-" + chunk_id,
        "generation_id": "gen-" + chunk_id,
        "content": text,
        "content_hash": fingerprint(text),
        "start_char": 0,
        "end_char": len(text),
    }


@pytest.fixture
def retrieval(monkeypatch):
    rows = [
        row("seed", "The original source evidence."),
        row("connected", "The connected source evidence."),
        row("other", "Other evidence."),
    ]
    calls = []
    vector_items = [{"chunk": rows[0], "score": 0.9}, {"chunk": rows[2], "score": 0.8}]
    graph_items = [
        {"chunk": rows[0], "score": 0.9, "method": "vector_seed", "path": []},
        {
            "chunk": rows[1],
            "score": None,
            "method": "graph_expansion",
            "path": [{"from_chunk_id": "seed", "chunk_id": "connected"}],
        },
    ]

    class Vectors:
        key = "vector-generation"
        provenance = None

        def require_publication(self):
            calls.append("vector_guard")

        def search(self, provider, message, limit):
            calls.append("vector_search")
            return vector_items

    vectors = Vectors()
    graph = SimpleNamespace(
        key="graph-generation",
        search=lambda *args: calls.append("graph_search")
        or {"results": graph_items, "graph_added": 1},
    )
    service = RetrievalService({}, {"id": "p", "organization_id": "o"})
    base = {
        "state": "text_ready",
        "capabilities": {"text": True, "vector": False, "graph": False},
        "counts": {"total": 3, "text_ready": 3},
        "documents": [
            {
                "state": "text_ready",
                "capabilities": {"text": True, "vector": False, "graph": False},
                "coverage": {"valid_chunks": 1},
            }
            for _ in rows
        ],
    }
    monkeypatch.setattr(service, "base_status", lambda: copy.deepcopy(base))

    @contextmanager
    def stores():
        try:
            yield {"rows": rows, "manifest": "manifest"}, None, vectors
        finally:
            calls.append("closed")

    monkeypatch.setattr(service, "stores", stores)
    monkeypatch.setattr(
        service, "graph", lambda vector_store: calls.append("graph_guard") or graph
    )
    return service, rows, vectors, graph, calls


@pytest.mark.parametrize(
    "mode,expected",
    [
        ("vector", {"vector_search"}),
        ("graph", {"graph_search"}),
        ("hybrid", {"vector_search", "graph_search"}),
    ],
)
def test_modes_execute_distinct_paths_and_keep_graph_context(retrieval, mode, expected):
    service, _, _, _, calls = retrieval
    result = service.retrieve("question", mode)
    assert {call for call in calls if call.endswith("_search")} == expected
    assert result["diagnostics"]["mode"] == mode and calls[-1] == "closed"
    if mode != "vector":
        assert {item["chunk"]["id"] for item in result["context"]} >= {
            "seed",
            "connected",
        }
    if mode == "hybrid":
        assert result["diagnostics"]["ranking"] == "reciprocal_rank_fusion_k60"
        assert len(result["candidates"]) == 3


@pytest.mark.parametrize("mode", ["graph", "hybrid"])
def test_unavailable_graph_never_silently_becomes_vector_only(
    retrieval, monkeypatch, mode
):
    service, _, _, _, calls = retrieval

    def unavailable(vectors):
        raise RetrievalUnavailable("graph_not_ready")

    monkeypatch.setattr(service, "graph", unavailable)
    with pytest.raises(RetrievalUnavailable, match="graph_not_ready"):
        service.retrieve("question", mode)
    assert (
        "vector_search" not in calls
        and "graph_search" not in calls
        and calls[-1] == "closed"
    )


def test_rank_fusion_deduplicates_and_rejects_foreign_or_fake_scores():
    source = row("one", "Evidence")
    item = {"chunk": source, "score": 0.8}
    result = rank_candidates(
        "hybrid", [item, item], [item | {"method": "vector_seed", "path": []}], [source]
    )
    assert len(result) == 1 and result[0]["fusion_score"] == pytest.approx(2 / 61)
    assert result[0]["vector_score"] == 0.8
    with pytest.raises(ValueError, match="Foreign"):
        rank_candidates(
            "vector",
            [item | {"chunk": source | {"document_id": "foreign"}}],
            [],
            [source],
        )
    with pytest.raises(ValueError, match="score"):
        rank_candidates("vector", [item | {"score": float("nan")}], [], [source])


def test_context_budget_preserves_whole_connected_paths(retrieval):
    service, _, _, _, _ = retrieval
    candidates = service.retrieve("question", "hybrid")["candidates"]
    assert select_context(candidates, "graph", byte_budget=10) == []
    selected = select_context(candidates, "hybrid", byte_budget=180)
    assert {item["chunk"]["id"] for item in selected} >= {"seed", "connected"}
    connected = next(item for item in candidates if item["path"])
    connected["path"][-1]["chunk_id"] = "other"
    with pytest.raises(ValueError, match="Disconnected"):
        select_context(candidates, "graph")


def test_hybrid_context_falls_back_to_ranked_candidates_without_graph_paths():
    candidates = [
        {
            "chunk": row("one", "Vector evidence."),
            "vector_score": 0.9,
            "fusion_score": 1 / 61,
            "methods": ["vector"],
            "path": [],
        }
    ]
    assert select_context(candidates, "hybrid") == candidates


def test_freshness_guard_rejects_changed_vector_or_graph_generations(retrieval):
    service, _, vectors, _, calls = retrieval
    with pytest.raises(RetrievalUnavailable, match="index_generation_changed"):
        service.verify("old-vector-generation", None, "vector")
    with pytest.raises(RetrievalUnavailable, match="graph_generation_changed"):
        service.verify(vectors.key, "old-graph-generation", "graph")
    assert calls[-1] == "closed"


def test_published_readiness_projects_precise_capabilities(retrieval):
    service, _, _, _, _ = retrieval
    status = service.status()
    assert status["state"] == "graphrag_ready" and status["capabilities"] == {
        "text": True,
        "vector": True,
        "graph": True,
    }
    assert all(
        item["coverage"]["verified_vectors"]
        == item["coverage"]["verified_graph_chunks"]
        == 1
        for item in status["documents"]
    )


def test_missing_retrieval_config_never_connects_to_any_store(store):
    repository, _, project = store
    repository.stage(project, "s", "record", "Canonical text")
    status = RetrievalService(
        {"TURSO_DATABASE_URL": repository.url, "TURSO_AUTH_TOKEN": repository.token},
        project,
    ).status()
    assert status["state"] == "text_ready" and status["capabilities"]["vector"] is False
    assert status["failures"][0]["code"] == "retrieval_not_configured"
