"""Opt-in real Neo4j + Flask/SQL wiring; controlled models, never corpus-quality evidence."""

import json
import os

import pytest

from backend.app import create_app
from backend.app.services.evidence_graph import EvidenceGraph
from backend.app.services.graph_extraction import GraphExtractor
from backend.app.services.neo4j_vectors import Neo4jVectorStore, canonical_snapshot
from backend.tests.test_evidence_graph import FixtureEmbeddings, FixtureLlm
from backend.tests.test_index_state import query


@pytest.mark.skipif(
    not os.environ.get("STAGE_E_TEST_NEO4J_URI"),
    reason="Requires explicitly supplied disposable Neo4j",
)
def test_actual_vector_graph_hybrid_flask_wiring_with_canonical_sources(
    store, monkeypatch
):
    repository, path, project = store
    repository.stage(project, "fixture", "one", "This judgment cited AIR 1967 SC 1326.")
    repository.stage(
        project, "fixture", "two", "This judgment distinguished AIR 1967 SC 1326."
    )
    for index in range(3):
        repository.stage(
            project,
            "fixture",
            "extra-" + str(index),
            f"This judgment cited AIR 1967 SC 1326. Additional fixture passage {index}.",
        )
    config = {
        "TURSO_DATABASE_URL": repository.url,
        "TURSO_AUTH_TOKEN": repository.token,
        "NEO4J_URI": os.environ["STAGE_E_TEST_NEO4J_URI"],
        "NEO4J_USERNAME": "neo4j",
        "NEO4J_PASSWORD": os.environ["STAGE_E_TEST_NEO4J_PASSWORD"],
    }
    snapshot = canonical_snapshot(config, project)
    provenance = {
        "provider": "ollama",
        "model": "synthetic-fixture-only:latest",
        "revision": "c" * 64,
        "dimensions": 768,
    }

    class Embeddings(FixtureEmbeddings):
        def revision(self):
            return provenance.copy()

    provider = Embeddings()
    llm = FixtureLlm()
    vectors = Neo4jVectorStore(config, snapshot, provenance)
    try:
        vectors.prepare()
        vectors.write_batch(
            snapshot["rows"],
            provider.embed_versioned(
                [row["content"] for row in snapshot["rows"]], provenance
            ),
        )
        vectors.publish()
        extractor = GraphExtractor(llm, vectors.key)
        graph = EvidenceGraph(vectors, extractor.profile)
        assert graph.build(extractor)["valid_extractions"] == 5
        graph.publish()
        monkeypatch.setattr(
            "backend.app.services.retrieval.embedding_provider_for_project",
            lambda *args: provider,
        )
        monkeypatch.setattr(
            "backend.app.services.retrieval.graph_extraction_llm", lambda *args: llm
        )

        def generate(config, messages):
            labels = [
                item["id"] for item in json.loads(messages[1]["content"])["evidence"]
            ]
            return json.dumps(
                {
                    "status": "answered",
                    "answer": "Fixture source evidence "
                    + " ".join("[" + label + "]" for label in labels),
                    "used_sources": labels,
                }
            ), {
                "provider": "controlled-test-only",
                "model": "fixture-response",
                "fallback": False,
            }

        monkeypatch.setattr(
            "backend.app.services.query_service.generate_grounded", generate
        )

        class Config:
            TESTING = True
            TURSO_DATABASE_URL = repository.url
            TURSO_AUTH_TOKEN = repository.token
            BACKEND_INTERNAL_SECRET = "fixture-secret"
            NEO4J_URI = config["NEO4J_URI"]
            NEO4J_USERNAME = config["NEO4J_USERNAME"]
            NEO4J_PASSWORD = config["NEO4J_PASSWORD"]

        client = create_app(Config).test_client()
        headers = {
            "X-Internal-Secret": "fixture-secret",
            "X-User-Id": "u",
            "X-Organization-Id": "o",
        }
        for mode in ("vector", "graph", "hybrid"):
            response = client.post(
                "/api/projects/p/query",
                headers=headers,
                json={"message": "seed query", "mode": mode},
            )
            assert response.status_code == 200, response.json
            assert response.json["mode"] == mode and response.json["sources"]
            if mode != "vector":
                assert response.json["graph_generation"] == graph.key
                assert response.json["retrieval_diagnostics"]["graph_added"] >= 1
                assert any(
                    "graph_expansion" in source["retrieval_methods"]
                    for source in response.json["sources"]
                )
            for citation in response.json["sources"]:
                resolved = client.get(citation["source_view_url"], headers=headers)
                assert (
                    resolved.status_code == 200
                    and resolved.json["content"] == citation["excerpt"]
                )
        assert query(path, "SELECT status FROM query_runs") == [("completed",)] * 3
        graph.withdraw()
        blocked = client.post(
            "/api/projects/p/query",
            headers=headers,
            json={"message": "seed query", "mode": "hybrid"},
        )
        assert blocked.status_code == 409
        assert query(path, "SELECT count(*) FROM query_runs") == [(3,)]
    finally:
        vectors.close()
