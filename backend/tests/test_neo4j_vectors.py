import json

import pytest

from backend.app.services.neo4j_vectors import Neo4jVectorStore
from backend.app.services.rag import fingerprint


@pytest.fixture
def store(monkeypatch):
    monkeypatch.setattr(
        "backend.app.services.neo4j_vectors.GraphDatabase.driver",
        lambda *args, **kwargs: None,
    )
    row = {
        "id": "chunk",
        "generation_id": "generation",
        "content": "A canonical source passage.",
        "content_hash": fingerprint("A canonical source passage."),
        "document_id": "doc",
        "chunk_index": 0,
        "start_char": 0,
        "end_char": 27,
        "source_pages": "[]",
        "source_metadata": "{}",
        "chunker_version": "test",
        "file_name": "case",
    }
    return Neo4jVectorStore(
        {"NEO4J_URI": "unused", "NEO4J_USERNAME": "unused", "NEO4J_PASSWORD": "unused"},
        {
            "organization_id": "org",
            "project_id": "project",
            "manifest": fingerprint([row]),
            "rows": [row],
        },
        {
            "provider": "ollama",
            "model": "model:latest",
            "revision": "a" * 64,
            "dimensions": 768,
        },
    )


def record(store):
    row = store.snapshot["rows"][0]
    vector = [1.0] * 768
    return {
        "chunk": store.properties(row)
        | {"embedding": vector, "vector_hash": fingerprint(vector)},
        "documents": [store.document_properties(row)],
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("organization_id", "foreign"),
        ("generation_id", "stale"),
        ("content", "changed"),
        ("embedding", [0.0] * 768),
        ("model_revision", "unknown"),
        ("vector_hash", "corrupt"),
    ],
)
def test_integrity_rejects_corrupt_or_foreign_chunks(store, monkeypatch, field, value):
    item = record(store)
    item["chunk"][field] = value
    monkeypatch.setattr(store, "records", lambda: [item])
    assert store.valid_ids() == set()
    with pytest.raises(ValueError, match="integrity"):
        store.valid_ids(complete=True)


def test_integrity_checks_document_links_and_duplicates(store, monkeypatch):
    item = record(store)
    monkeypatch.setattr(store, "records", lambda: [item])
    assert store.valid_ids(complete=True) == {"chunk"}
    item["documents"] = []
    with pytest.raises(ValueError):
        store.valid_ids(complete=True)
    monkeypatch.setattr(store, "records", lambda: [record(store), record(store)])
    with pytest.raises(ValueError, match="duplicate"):
        store.valid_ids()


def test_partition_identity_includes_tenant_manifest_and_model(store):
    config = {
        "NEO4J_URI": "unused",
        "NEO4J_USERNAME": "unused",
        "NEO4J_PASSWORD": "unused",
    }
    for change in (
        {"organization_id": "other"},
        {"project_id": "other"},
        {"manifest": "new"},
    ):
        assert (
            Neo4jVectorStore(config, store.snapshot | change, store.provenance).index
            != store.index
        )
    assert (
        Neo4jVectorStore(
            config, store.snapshot, store.provenance | {"revision": "b" * 64}
        ).index
        != store.index
    )


def test_partial_build_resumes_and_does_not_publish(store, monkeypatch):
    calls = []
    monkeypatch.setattr(store, "prepare", lambda: None)
    monkeypatch.setattr(store, "index_status", lambda: None)
    monkeypatch.setattr(store, "checkpoint", lambda *args: calls.append(args))
    monkeypatch.setattr(store, "valid_ids", lambda **kwargs: {"chunk"})

    class Provider:
        def embed_versioned(self, *args):
            pytest.fail("Valid vector should not be embedded again")

    assert store.build(Provider())["reused_vectors"] == 1
    assert calls[-1] == ("verified_unpublished", 1)


def test_build_failure_retains_retry_checkpoint(store, monkeypatch):
    calls = []
    monkeypatch.setattr(store, "prepare", lambda: None)
    monkeypatch.setattr(store, "valid_ids", lambda **kwargs: set())
    monkeypatch.setattr(store, "checkpoint", lambda *args: calls.append(args))

    class Provider:
        def embed_versioned(self, texts, provenance):
            assert texts == ["A canonical source passage."]
            raise TimeoutError("private transport details")

    with pytest.raises(TimeoutError):
        store.build(Provider())
    assert calls[-1] == ("failed", 0, "TimeoutError")


def test_batch_rejects_invalid_vectors_and_foreign_rows_before_write(store):
    with pytest.raises(ValueError):
        store.write_batch(store.snapshot["rows"], [[1.0]])
    with pytest.raises(ValueError, match="outside"):
        store.write_batch(
            [store.snapshot["rows"][0] | {"content": "foreign"}], [[1.0] * 768]
        )


def test_search_uses_partitioned_top_k_and_refuses_foreign_result(store, monkeypatch):
    monkeypatch.setattr(store, "index_status", lambda: None)
    monkeypatch.setattr(store, "valid_ids", lambda **kwargs: {"chunk"})
    item = record(store)

    def run(query, **params):
        if "RAGVectorPublication" in query:
            return [
                {
                    "publication": {
                        "manifest": store.snapshot["manifest"],
                        "provenance": json.dumps(store.provenance, sort_keys=True),
                        "expected_chunks": 1,
                        "organization_id": "org",
                        "project_id": "project",
                    }
                }
            ]
        assert "db.index.vector.queryNodes" in query
        assert params["index"] == store.index and params["limit"] == 8
        return [{"chunk": item["chunk"].copy(), "score": 0.9}]

    monkeypatch.setattr(store, "_run", run)

    class Provider:
        def embed_versioned(self, texts, provenance):
            return [[1.0] * 768]

    result = store.search(Provider(), "semantic question")
    assert result[0]["score"] == 0.9 and "embedding" not in result[0]["chunk"]
    item["chunk"]["organization_id"] = "foreign"
    with pytest.raises(ValueError, match="Foreign"):
        store.search(Provider(), "semantic question")
    monkeypatch.setattr(store, "_run", lambda *args, **kwargs: [])
    with pytest.raises(ValueError, match="not published"):
        store.search(Provider(), "semantic question")


def test_index_configuration_is_checked_not_just_its_name(store, monkeypatch):
    index = {
        "state": "ONLINE",
        "labelsOrTypes": [store.label],
        "properties": ["embedding"],
        "options": {
            "indexConfig": {
                "vector.dimensions": 768,
                "vector.similarity_function": "COSINE",
            }
        },
    }
    monkeypatch.setattr(store, "_run", lambda *args, **kwargs: [index])
    assert store.index_status() == index
    index["state"] = "POPULATING"
    with pytest.raises(ValueError, match="unavailable"):
        store.index_status()
