"""Opt-in real-service checks on a DISPOSABLE Neo4j, never the application store."""

import os

import pytest

from backend.app.services.embedding_service import EmbeddingGemmaProvider
from backend.app.services.neo4j_vectors import Neo4jVectorStore
from backend.app.services.rag import fingerprint


@pytest.mark.skipif(
    not os.environ.get("STAGE_C_TEST_NEO4J_URI"),
    reason="Requires explicitly supplied disposable Neo4j",
)
def test_real_index_resume_scope_corruption_and_publication_rollback():
    config = {
        "NEO4J_URI": os.environ["STAGE_C_TEST_NEO4J_URI"],
        "NEO4J_USERNAME": "neo4j",
        "NEO4J_PASSWORD": os.environ["STAGE_C_TEST_NEO4J_PASSWORD"],
    }
    provider = EmbeddingGemmaProvider(
        os.environ.get("STAGE_C_TEST_OLLAMA_URL", "http://localhost:11434"),
        "embeddinggemma",
    )
    provenance = provider.resolve()
    stores = []
    try:
        for org, text in (
            (
                "integration-org",
                "An employee may challenge an unlawful dismissal in court.",
            ),
            (
                "foreign-org",
                "An employee may challenge an unlawful dismissal in court.",
            ),
        ):
            row = {
                "id": "integration-chunk",
                "document_id": "integration-doc",
                "generation_id": "integration-gen",
                "content": text,
                "content_hash": fingerprint(text),
                "chunk_index": 0,
                "start_char": 0,
                "end_char": len(text),
                "source_pages": "[]",
                "source_metadata": "{}",
                "chunker_version": "integration",
                "file_name": "integration-test",
            }
            snapshot = {
                "organization_id": org,
                "project_id": "integration-project",
                "rows": [row],
                "manifest": fingerprint([row]),
            }
            store = Neo4jVectorStore(config, snapshot, provenance)
            stores.append(store)
            assert store.build(provider, batch_size=1)["verified_vectors"] == 1
            assert store.build(provider)["reused_vectors"] == 1
            with pytest.raises(ValueError, match="not published"):
                store.search(provider, "How can a worker contest being fired?")
            result = store.search(
                provider,
                "How can a worker contest being fired?",
                require_publication=False,
            )
            assert len(result) == 1 and result[0]["chunk"]["organization_id"] == org
            assert 0 < result[0]["score"] <= 1
            store.publish()
            assert store.search(provider, "How can a worker contest being fired?")
            store.withdraw()
            with pytest.raises(ValueError, match="not published"):
                store.search(provider, "How can a worker contest being fired?")
            assert store.valid_ids(complete=True) == {"integration-chunk"}
        target = stores[0]
        target._run(f"MATCH (c:{target.label}) SET c.embedding=[0.0]", write=True)
        with pytest.raises(ValueError, match="integrity"):
            target.valid_ids(complete=True)
        assert target.build(provider)["reused_vectors"] == 0
        assert stores[1].valid_ids(complete=True) == {"integration-chunk"}
    finally:
        for store in stores:
            store.close()
