import json

import httpx
import pytest

from backend.app.services.graph_extraction import (
    ExtractionError,
    GraphExtractor,
    entity_identity,
    validate_extraction,
)
from backend.app.services.llm_client import graph_extraction_llm
from backend.app.services.rag import fingerprint


def chunk(text, document="doc", offset=50):
    return {"id": fingerprint([document, offset, text]), "document_id": document, "generation_id": "generation",
            "content": text, "content_hash": fingerprint(text), "start_char": offset, "end_char": offset + len(text)}


def cited_payload(text="This judgment cited AIR 1967 SC 1326."):
    return {"entities": [{"name": "AIR 1967 SC 1326", "type": "Case"}],
            "relations": [{"source": -1, "target": 0, "relation": "CITES", "quote": text}]}


def test_exact_citation_resolution_keeps_all_source_occurrences():
    text = "This judgment cited AIR 1967 SC 1326. " * 2
    row = chunk(text)
    result = validate_extraction(cited_payload(), row, "graph")
    assert len(result["entities"][0]["mentions"]) == len(result["assertions"][0]["evidence"]) == 2
    for span in result["assertions"][0]["evidence"]:
        assert text[span["start_char"] - 50:span["end_char"] - 50] == span["quote"]
        assert span["chunk_id"] == row["id"] and span["document_id"] == "doc"
    second = validate_extraction(cited_payload(), chunk(text, "other"), "graph")
    assert result["entities"][0]["key"] == second["entities"][0]["key"]
    assert result["assertions"][0]["key"] != second["assertions"][0]["key"]


def test_namesakes_are_not_merged_across_documents_or_graph_generations():
    person = {"name": "Ram Narain", "type": "Person"}
    assert entity_identity(person, {"document_id": "one"}, "graph") != entity_identity(person, {"document_id": "two"}, "graph")
    assert entity_identity(person, {"document_id": "one"}, "graph") != entity_identity(person, {"document_id": "one"}, "other-graph")
    citation = {"name": "A.I.R. 1967 S.C. 1326", "type": "Case"}
    plain = {"name": "AIR 1967 SC 1326", "type": "Case"}
    assert entity_identity(citation, {"document_id": "one"}, "graph") == entity_identity(plain, {"document_id": "two"}, "graph")


@pytest.mark.parametrize("text,kind", [
    ("This judgment did not overrule AIR 1967 SC 1326.", "OVERRULES"),
    ("Whether this judgment overruled AIR 1967 SC 1326 is disputed.", "OVERRULES"),
    ("This judgment mentioned AIR 1967 SC 1326.", "DISTINGUISHES"),
    ("This judgment refused to distinguish AIR 1967 SC 1326.", "DISTINGUISHES"),
])
def test_negated_uncertain_and_cooccurrence_relations_are_rejected(text, kind):
    payload = cited_payload(text)
    payload["relations"][0]["relation"] = kind
    with pytest.raises(ExtractionError, match="unsupported_relation"):
        validate_extraction(payload, chunk(text), "graph")


def test_reversed_active_relation_and_wrong_endpoint_types_are_rejected():
    text = "Case Alpha overruled Case Beta."
    payload = {"entities": [{"name": "Case Alpha", "type": "Case"}, {"name": "Case Beta", "type": "Case"}],
               "relations": [{"source": 1, "target": 0, "relation": "OVERRULES", "quote": text}]}
    with pytest.raises(ExtractionError, match="unsupported_relation"):
        validate_extraction(payload, chunk(text), "graph")
    payload["relations"][0].update(source=0, target=1)
    assert validate_extraction(payload, chunk(text), "graph")["assertions"][0]["relation"] == "OVERRULES"
    payload["entities"][1]["type"] = "Person"
    with pytest.raises(ExtractionError, match="invalid_endpoints"):
        validate_extraction(payload, chunk(text), "graph")


def test_fabricated_evidence_and_corrupt_canonical_text_are_rejected():
    row = chunk("This judgment cited AIR 1967 SC 1326.")
    payload = cited_payload("This judgment overruled AIR 1967 SC 1326.")
    with pytest.raises(ExtractionError, match="invalid_evidence"):
        validate_extraction(payload, row, "graph")
    row["content_hash"] = "corrupt"
    with pytest.raises(ExtractionError, match="canonical_integrity_failed"):
        validate_extraction(cited_payload(), row, "graph")


class Llm:
    def __init__(self):
        self.options = {"temperature": 0}

    def revision(self):
        return {"model": "test:latest", "revision": "a" * 64}

    def generate(self, prompt):
        assert "SOURCE_JSON=" in prompt
        assert json.loads(prompt.split("SOURCE_JSON=", 1)[1])["text"] == "This judgment cited AIR 1967 SC 1326."
        return json.dumps(cited_payload())


def test_extractor_calls_the_llm_on_actual_canonical_text():
    extractor = GraphExtractor(Llm(), "vectors")
    assert extractor.extract(chunk("This judgment cited AIR 1967 SC 1326."))["method"] == "llm_explicit_quote"


@pytest.mark.parametrize("failure,code", [(httpx.ReadTimeout("private details"), "timeout"),
                                        (httpx.ConnectError("secret endpoint"), "provider_error")])
def test_provider_failures_are_visible_and_secret_safe(failure, code):
    class Failed(Llm):
        def generate(self, prompt):
            raise failure
    with pytest.raises(ExtractionError, match="^" + code + "$"):
        GraphExtractor(Failed(), "vectors").extract(chunk("This judgment cited AIR 1967 SC 1326."))


def test_parse_failure_and_model_drift_never_return_synthetic_graphs():
    class Malformed(Llm):
        def generate(self, prompt):
            return "not JSON"
    with pytest.raises(ExtractionError, match="parse_error"):
        GraphExtractor(Malformed(), "vectors").extract(chunk("text"))
    llm = Llm()
    extractor = GraphExtractor(llm, "vectors")
    llm.revision = lambda: {"model": "test:latest", "revision": "b" * 64}
    with pytest.raises(ExtractionError, match="model_changed"):
        extractor.extract(chunk("text"))


@pytest.mark.parametrize("timeout", [0, -1, float("inf"), 121])
def test_graph_requests_always_have_bounded_timeouts(timeout):
    with pytest.raises(ValueError, match="timeout"):
        graph_extraction_llm({"GRAPH_LLM_TIMEOUT_SECONDS": timeout})
