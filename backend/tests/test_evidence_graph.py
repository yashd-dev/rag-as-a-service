import json
import os
import uuid
from types import SimpleNamespace

import httpx
import pytest

from backend.app.services.evidence_graph import EvidenceGraph
from backend.app.services.graph_extraction import GraphExtractor
from backend.app.services.neo4j_vectors import Neo4jVectorStore
from backend.app.services.rag import fingerprint
from backend.scripts import index_graph


def test_graph_cli_default_plan_cannot_call_models_or_neo4j(store, tmp_path, monkeypatch, capsys):
    repository, path, project = store
    repository.stage(project, "source", "record", "Existing canonical source text.")
    env = tmp_path / "graph.env"
    env.write_text(f"TURSO_DATABASE_URL={repository.url}\nTURSO_AUTH_TOKEN=local\n")
    def forbidden(*args, **kwargs):
        pytest.fail("Graph plan must not call a model or Neo4j")
    monkeypatch.setattr(index_graph, "Neo4jVectorStore", forbidden)
    monkeypatch.setattr(index_graph, "GraphExtractor", forbidden)
    before = path.read_bytes()
    assert index_graph.main(["--env-file", str(env), "--organization-id", "o", "--project-id", "p"]) == 0
    assert path.read_bytes() == before
    assert json.loads(capsys.readouterr().out)["model_calls"] is False


def test_graph_retrieval_rejects_unbounded_budgets_and_foreign_neighbors():
    vectors = SimpleNamespace(key="vectors", snapshot={"organization_id": "org", "project_id": "p", "rows": [{"id": "seed"}]},
                              search=lambda *args: [{"chunk": {"id": "seed"}, "score": 0.8}])
    graph = EvidenceGraph(vectors, {})
    graph.integrity = lambda: None
    graph.neighbors = lambda *args: [{"chunk_id": "foreign", "left": {}, "right": {}}]
    with pytest.raises(ValueError, match="budget"):
        graph.search(None, "query", hops=100, require_publication=False)
    with pytest.raises(ValueError, match="Foreign"):
        graph.search(None, "query", require_publication=False)


class FixtureLlm:
    """Controlled structured responses for storage/traversal tests, not model-quality evidence."""
    def __init__(self, revision="a" * 64, empty=False):
        self.options = {"temperature": 0, "seed": 1 if empty else 0}
        self.digest, self.empty, self.calls, self.fail = revision, empty, 0, False

    def revision(self):
        return {"model": "synthetic-fixture-only:latest", "revision": self.digest}

    def generate(self, prompt):
        self.calls += 1
        if self.fail:
            raise httpx.ReadTimeout("private connection details")
        text = json.loads(prompt.split("SOURCE_JSON=", 1)[1])["text"]
        if self.empty:
            return json.dumps({"entities": [], "relations": []})
        return json.dumps({"entities": [{"name": "AIR 1967 SC 1326", "type": "Case"}],
                           "relations": [{"source": -1, "target": 0, "relation": "CITES" if "cited" in text else "DISTINGUISHES", "quote": text}]})


class FixtureEmbeddings:
    def embed_versioned(self, texts, provenance):
        return [[1.0, 0.0] + [0.0] * 766 if "distinguished" not in text else [0.0, 1.0] + [0.0] * 766 for text in texts]


@pytest.mark.skipif(not os.environ.get("STAGE_D_TEST_NEO4J_URI"), reason="Requires explicitly supplied disposable Neo4j")
def test_real_neo4j_graph_evidence_retry_integrity_scope_and_connected_retrieval(monkeypatch):
    config = {"NEO4J_URI": os.environ["STAGE_D_TEST_NEO4J_URI"], "NEO4J_USERNAME": "neo4j",
              "NEO4J_PASSWORD": os.environ["STAGE_D_TEST_NEO4J_PASSWORD"]}
    embeddings = FixtureEmbeddings()
    stores, graphs = [], []
    try:
        suffix = uuid.uuid4().hex
        for org in ("graph-fixture-org-" + suffix, "foreign-fixture-org-" + suffix):
            rows = []
            for index, text in enumerate(("This judgment cited AIR 1967 SC 1326.", "This judgment distinguished AIR 1967 SC 1326.")):
                rows.append({"id": fingerprint([org, index, text]), "document_id": "doc-" + str(index), "generation_id": "generation-" + str(index),
                             "content": text, "content_hash": fingerprint(text), "start_char": 0, "end_char": len(text),
                             "chunk_index": 0, "source_pages": "[]", "source_metadata": "{}", "chunker_version": "fixture-only", "file_name": "fixture"})
            vectors = Neo4jVectorStore(config, {"organization_id": org, "project_id": "fixture-project", "rows": rows, "manifest": fingerprint(rows)},
                                       {"provider": "ollama", "model": "synthetic-fixture-only:latest", "revision": "c" * 64, "dimensions": 768})
            stores.append(vectors)
            vectors.prepare()
            vectors.write_batch(rows, embeddings.embed_versioned([row["content"] for row in rows], vectors.provenance))
            llm = FixtureLlm()
            extractor = GraphExtractor(llm, vectors.key)
            graph = EvidenceGraph(vectors, extractor.profile)
            graphs.append(graph)
            with pytest.raises(ValueError, match="Stage C"):
                graph.build(extractor)
            vectors.publish()
            partial = graph.build(extractor, max_chunks=1)
            assert partial["state"] == "graph_partial" and partial["valid_extractions"] == 1 and partial["failures"]
            status = graph.build(extractor)
            assert status["valid_extractions"] == 2 and status["entities"] == 1 and status["assertions"] == 2
            assert status["evidence_spans"] == 4 and llm.calls == 2
            assert len(status["assertion_samples"]) == 2 and status["assertion_samples"][0]["evidence"]
            assert graph.build(extractor)["reused"] == 2 and llm.calls == 2
            with pytest.raises(ValueError, match="not published"):
                graph.search(embeddings, "seed query", seed_limit=1)
            result = graph.search(embeddings, "seed query", seed_limit=1, require_publication=False)
            assert result["seed_count"] == 1 and result["graph_added"] == 1
            added = result["results"][1]
            assert added["chunk"]["document_id"] == "doc-1" and added["score"] is None
            assert added["path"][0]["relation"] == "CITES"
            for side in ("left", "right"):
                span = added["path"][0][side]
                original = graph.rows[span["chunk_id"]]
                assert original["content"][span["start_char"]:span["end_char"]] == span["quote"]
                assert span["organization_id"] == org
            original_neighbors = graph.neighbors
            def changed_path(row, fanout, read_neighbors=original_neighbors):
                edges = read_neighbors(row, fanout)
                return [edge | {"left": edge["left"] | {"quote": "invented after integrity check"}} for edge in edges]
            with monkeypatch.context() as patch:
                patch.setattr(graph, "neighbors", changed_path)
                with pytest.raises(ValueError, match="path evidence changed"):
                    graph.search(embeddings, "seed query", seed_limit=1, require_publication=False)
            graph.publish()
            assert graph.search(embeddings, "seed query", seed_limit=1)["graph_added"] == 1
            assert graph.build(extractor)["reused"] == 2 and llm.calls == 2
            with pytest.raises(ValueError, match="not published"):
                graph.search(embeddings, "seed query", seed_limit=1)
            graph.publish()
            graph.withdraw()
            with pytest.raises(ValueError, match="not published"):
                graph.search(embeddings, "seed query", seed_limit=1)
            vectors._run("MATCH (e:RAGEvidence {graph_key:$graph}) SET e.start_char=999", write=True, graph=graph.key)
            with pytest.raises(ValueError, match="integrity"):
                graph.integrity()
            assert graph.build(extractor)["valid_extractions"] == 2 and llm.calls == 2
            graph.attempt(rows[0], "storage_error")
            assert graph.integrity(complete=False)["valid_extractions"] == 1
            with pytest.raises(ValueError, match="incomplete"):
                graph.integrity()
            assert graph.build(extractor)["valid_extractions"] == 2 and llm.calls == 3
        assert graphs[0].key != graphs[1].key
        assert graphs[0].integrity()["entities"] == 1
        vectors = stores[0]
        failed_llm = FixtureLlm(revision="b" * 64)
        failed_llm.fail = True
        extractor = GraphExtractor(failed_llm, vectors.key)
        graph = EvidenceGraph(vectors, extractor.profile)
        failed = graph.build(extractor, max_chunks=1)
        assert failed["state"] == "graph_partial" and failed["valid_extractions"] == 0
        assert failed["failures"][0]["code"] == "timeout"
        failed_llm.fail = False
        assert graph.build(extractor)["valid_extractions"] == 2
        empty_extractor = GraphExtractor(FixtureLlm(empty=True), vectors.key)
        empty_graph = EvidenceGraph(vectors, empty_extractor.profile)
        empty = empty_graph.build(empty_extractor)
        assert empty["state"] == "graph_partial" and empty["empty_extractions"] == 2 and empty["entities"] == 0
        with pytest.raises(ValueError, match="no supported assertions"):
            empty_graph.publish()
        assert empty_graph.search(embeddings, "seed query", seed_limit=1, require_publication=False)["state"] == "no_connected_evidence"
    finally:
        for store in stores:
            store.close()
