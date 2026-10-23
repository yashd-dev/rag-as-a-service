import copy
import json
import os
import uuid
from types import SimpleNamespace

import httpx
import pytest

from backend.app.services import citation_extraction as citations
from backend.app.services.evidence_graph import EvidenceGraph
from backend.app.services.graph_extraction import (
    ExtractionError,
    GraphExtractor,
    graph_extractor_for_project,
)
from backend.app.services.neo4j_vectors import Neo4jVectorStore
from backend.app.services.rag import fingerprint
from backend.scripts import index_graph
from backend.tests.test_evidence_graph import FixtureEmbeddings
from backend.tests.test_graph_extraction import chunk


@pytest.fixture
def extractor(monkeypatch):
    resolver = SimpleNamespace(
        base_url="http://local",
        model="qwen3:1.7b",
        timeout=60,
        options={"num_ctx": 4096},
        revision=lambda: {"model": "qwen3:1.7b", "revision": "a" * 64},
    )
    monkeypatch.setattr(citations, "graph_extraction_llm", lambda config: resolver)
    return citations.CitationCandidateExtractor({}, "vector-generation")


def test_citation_plan_preserves_exact_mentions_and_excludes_negated_assertions():
    row = chunk(
        "This judgment cited AIR 1967 SC 1326. It did not cite AIR 1967 SC 1326."
    )
    entities, candidates = citations.citation_plan(row, "graph")
    assert entities == [{"name": "AIR 1967 SC 1326", "type": "Case"}]
    assert len(candidates) == 1 and candidates[0]["quote"] == "cited AIR 1967 SC 1326"
    result = citations.validate_candidate_payload(
        {"entities": entities, "relations": candidates}, row, "graph"
    )
    assert len(result["entities"][0]["mentions"]) == 2
    assert (
        result["method"] == "citation_pattern_llm_verification"
        and result["candidate_decisions"] == 1
    )


def test_no_candidates_or_cue_does_not_call_a_model(extractor, monkeypatch):
    monkeypatch.setattr(
        citations.httpx,
        "post",
        lambda *args, **kwargs: pytest.fail(
            "No affirmative candidate should call inference"
        ),
    )
    empty = extractor.extract(chunk("An ordinary source paragraph without citations."))
    mention = extractor.extract(chunk("The printed reference is AIR 1967 SC 1326."))
    assert empty["entities"] == [] and empty["candidate_decisions"] == 0
    assert extractor.inference_calls == 0
    assert (
        mention["entities"]
        and mention["assertions"] == []
        and mention["method"] == "citation_pattern"
    )


def test_source_hash_is_checked_before_sending_text_to_model(extractor, monkeypatch):
    row = chunk("This judgment cited AIR 1967 SC 1326.")
    row["content_hash"] = "changed"
    monkeypatch.setattr(
        citations.httpx,
        "post",
        lambda *args, **kwargs: pytest.fail("Corrupt text must not leave staging"),
    )
    with pytest.raises(ExtractionError, match="canonical_integrity_failed"):
        extractor.extract(row)


def test_more_than_eight_citations_fails_visibly_instead_of_silently_truncating():
    row = chunk(" ".join(f"AIR 1967 SC {page}" for page in range(10, 19)))
    with pytest.raises(ExtractionError, match="citation_candidate_overflow"):
        citations.citation_plan(row, "graph")


@pytest.mark.parametrize("supported", [True, False])
def test_only_llm_support_decision_controls_candidate_relation(
    extractor, monkeypatch, supported
):
    decode = json.loads

    def post(url, *, json, timeout):
        assert url == "http://local/api/chat" and timeout == 60
        assert json["think"] is False and json["options"]["num_predict"] == 64
        data = decode(json["messages"][1]["content"])
        assert (
            data["case_citation"] == "AIR 1967 SC 1326"
            and data["source"] == "cited AIR 1967 SC 1326"
        )
        return httpx.Response(
            200,
            json={
                "message": {"content": '{"supported": ' + str(supported).lower() + "}"}
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(citations.httpx, "post", post)
    result = extractor.extract(chunk("This judgment cited AIR 1967 SC 1326."))
    assert bool(result["assertions"]) == supported and result["entities"]
    assert result["extractor_version"] == citations.VERSION
    assert extractor.inference_calls == 1


@pytest.mark.parametrize(
    "response", ['{"supported":"yes"}', '{"supported":true,"extra":1}', "not json"]
)
def test_malformed_classifier_response_fails_closed(extractor, monkeypatch, response):
    monkeypatch.setattr(
        citations.httpx,
        "post",
        lambda url, **kwargs: httpx.Response(
            200,
            json={"message": {"content": response}},
            request=httpx.Request("POST", url),
        ),
    )
    with pytest.raises(ExtractionError, match="parse_error"):
        extractor.extract(chunk("This judgment cited AIR 1967 SC 1326."))


def test_classifier_timeout_and_model_drift_are_explicit(extractor, monkeypatch):
    def timeout(*args, **kwargs):
        raise httpx.ReadTimeout("secret endpoint details")

    monkeypatch.setattr(citations.httpx, "post", timeout)
    with pytest.raises(ExtractionError, match="^timeout$"):
        extractor.extract(chunk("This judgment cited AIR 1967 SC 1326."))
    extractor.resolver.revision = lambda: {"model": "qwen3:1.7b", "revision": "b" * 64}
    with pytest.raises(ExtractionError, match="model_changed"):
        extractor.extract(chunk("This judgment cited AIR 1967 SC 1326."))


def test_model_drift_after_response_cannot_be_cached(extractor, monkeypatch):
    def post(url, **kwargs):
        extractor.resolver.revision = lambda: {
            "model": "qwen3:1.7b",
            "revision": "b" * 64,
        }
        return httpx.Response(
            200,
            json={"message": {"content": '{"supported":true}'}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(citations.httpx, "post", post)
    with pytest.raises(ExtractionError, match="model_changed"):
        extractor.extract(chunk("This judgment cited AIR 1967 SC 1326."))


def test_cached_candidate_payload_cannot_add_foreign_entities_or_relations(extractor):
    row = chunk("This judgment cited AIR 1967 SC 1326.")
    entities, relations = citations.citation_plan(row, extractor.key)
    valid = {"entities": entities, "relations": relations}
    result = citations.validate_candidate_payload(valid, row, extractor.key)
    vectors = SimpleNamespace(
        key="vector-generation",
        snapshot={"organization_id": "o", "project_id": "p", "rows": [row]},
        properties=lambda row: {"key": "vector-chunk"},
    )
    graph = EvidenceGraph(vectors, extractor.profile)
    assert graph.key == extractor.key
    record = graph.scope | {
        "key": fingerprint([graph.key, row["id"]]),
        "state": "extracted",
        "chunk_id": row["id"],
        "content_hash": row["content_hash"],
        "profile_json": json.dumps(extractor.profile, sort_keys=True),
        "chunk_keys": ["vector-chunk"],
        "result_json": json.dumps(valid),
        "result_hash": fingerprint(result),
    }
    assert graph.cached_result(row, record) == result
    forged = copy.deepcopy(valid)
    forged["entities"].append({"name": "judgment", "type": "Person"})
    with pytest.raises(ExtractionError, match="invalid_citation_candidates"):
        graph.validate_payload(forged, row)
    forged = copy.deepcopy(valid)
    forged["relations"][0]["quote"] = "invented quote"
    with pytest.raises(ExtractionError, match="invalid_citation_candidates"):
        graph.validate_payload(forged, row)


def test_full_extractor_stays_default_and_unknown_strategy_never_initializes_model(
    monkeypatch,
):
    llm = SimpleNamespace(
        options={}, revision=lambda: {"model": "fixture", "revision": "a" * 64}
    )
    monkeypatch.setattr(
        "backend.app.services.llm_client.graph_extraction_llm", lambda config: llm
    )
    default = graph_extractor_for_project({}, "vectors")
    assert isinstance(default, GraphExtractor)
    assert default.profile == GraphExtractor(llm, "vectors").profile
    with pytest.raises(ValueError, match="Unsupported graph extraction strategy"):
        graph_extractor_for_project({"GRAPH_EXTRACTION_STRATEGY": "unknown"}, "vectors")


def test_cli_overrides_are_process_local_and_keep_plan_read_only(
    store, tmp_path, monkeypatch, capsys
):
    repository, path, project = store
    repository.stage(project, "s", "record", "Existing source.")
    env = tmp_path / "citation-plan.env"
    env.write_text(
        f"TURSO_DATABASE_URL={repository.url}\nTURSO_AUTH_TOKEN=local\nGRAPH_LLM_MODEL=smollm2:135m\nGRAPH_EXTRACTION_STRATEGY=full_legal\n"
    )
    before = path.read_bytes(), env.read_bytes()
    monkeypatch.setattr(
        index_graph,
        "graph_extractor_for_project",
        lambda *args: pytest.fail("Plan must not load model identity"),
    )
    assert (
        index_graph.main(
            [
                "--env-file",
                str(env),
                "--organization-id",
                "o",
                "--project-id",
                "p",
                "--strategy",
                "citation_candidates",
                "--model",
                "qwen3:1.7b",
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert (
        result["strategy"] == "citation_candidates"
        and result["requested_model"] == "qwen3:1.7b"
    )
    assert (
        result["model_calls"] is False
        and (path.read_bytes(), env.read_bytes()) == before
    )


@pytest.mark.skipif(
    not os.environ.get("STAGE_D_TEST_NEO4J_URI"),
    reason="Requires explicitly supplied disposable Neo4j",
)
def test_opt_in_strategy_persists_and_reuses_its_own_validated_proofs(
    extractor, monkeypatch
):
    # Controlled classifier/vectors exercise storage and traversal, not model-quality acceptance.
    config = {
        "NEO4J_URI": os.environ["STAGE_D_TEST_NEO4J_URI"],
        "NEO4J_USERNAME": "neo4j",
        "NEO4J_PASSWORD": os.environ["STAGE_D_TEST_NEO4J_PASSWORD"],
    }
    rows = []
    for index, text in enumerate(
        (
            "This judgment cited AIR 1967 SC 1326.",
            "This judgment also cited AIR 1967 SC 1326.",
        )
    ):
        rows.append(
            chunk(text, document="citation-doc-" + str(index), offset=0)
            | {
                "chunk_index": 0,
                "source_pages": "[]",
                "source_metadata": "{}",
                "chunker_version": "fixture-only",
                "file_name": "fixture-only",
            }
        )
    snapshot = {
        "organization_id": "citation-fixture-" + uuid.uuid4().hex,
        "project_id": "fixture-project",
        "manifest": fingerprint(rows),
        "rows": rows,
    }
    vectors = Neo4jVectorStore(
        config,
        snapshot,
        {
            "provider": "ollama",
            "model": "synthetic-fixture-only",
            "revision": "c" * 64,
            "dimensions": 768,
        },
    )
    calls = []

    def post(url, **kwargs):
        calls.append(url)
        return httpx.Response(
            200,
            json={"message": {"content": '{"supported":true}'}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(citations.httpx, "post", post)
    provider = FixtureEmbeddings()
    try:
        vectors.prepare()
        vectors.write_batch(
            rows,
            provider.embed_versioned(
                [row["content"] for row in rows], vectors.provenance
            ),
        )
        vectors.publish()
        candidate = citations.CitationCandidateExtractor({}, vectors.key)
        graph = EvidenceGraph(vectors, candidate.profile)
        status = graph.build(candidate)
        assert (
            status["valid_extractions"] == 2
            and status["entities"] == 1
            and status["assertions"] == 2
        )
        assert len(calls) == 2
        assert graph.build(candidate)["reused"] == 2 and len(calls) == 2
        result = graph.search(
            provider, "seed query", seed_limit=1, require_publication=False
        )
        assert result["graph_added"] == 1
        vectors._run(
            "MATCH (e:RAGEvidence {graph_key:$graph}) SET e.quote='corrupt'",
            write=True,
            graph=graph.key,
        )
        with pytest.raises(ValueError, match="integrity"):
            graph.integrity()
        assert graph.build(candidate)["valid_extractions"] == 2 and len(calls) == 2
    finally:
        vectors.close()
