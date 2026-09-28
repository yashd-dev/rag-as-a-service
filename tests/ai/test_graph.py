from ai.graph.extractor import (
    entity_id,
    graph_extraction_prompt,
    graph_json_stats,
    normalize_entity_name,
    parse_graph_json,
)
from backend.app.services.llm_client import (
    GRAPH_EXTRACTION_SCHEMA,
    graph_extraction_llm,
)


def test_normalize_entity_name():
    assert normalize_entity_name("  'Supreme   Court'  ") == "supreme court"


def test_entity_id_is_stable():
    assert entity_id("p1", "article 21") == entity_id("p1", "article 21")


def test_parse_graph_json():
    entities, relations = parse_graph_json(
        '{"entities":[{"name":"Article 21","type":"law"}],"relations":[{"source":"Court","target":"Article 21","relation":"interprets"}]}'
    )

    assert entities[0].normalized_name == "article 21"
    assert relations[0].relation == "interprets"


def test_parse_graph_json_accepts_entity_field():
    entities, _relations = parse_graph_json(
        '{"entities":[{"entity":"Teacher-in-Charge","type":"role"}],"relations":[]}'
    )

    assert entities[0].name == "Teacher-in-Charge"


def test_graph_json_stats_counts_discarded_placeholders():
    payload = '{"entities":[{"name":"..."}],"relations":[{"source":"Entity name","target":"Article 21","relation":"..."}]}'

    entities, relations = parse_graph_json(payload)
    stats = graph_json_stats(payload)

    assert entities == []
    assert relations == []
    assert stats["raw_entities"] == 1
    assert stats["raw_relations"] == 1
    assert stats["placeholder_entities"] == 1
    assert stats["placeholder_relations"] == 1


def test_graph_extraction_contract_is_compact_and_bounded():
    prompt = graph_extraction_prompt("Article 21 was interpreted by the Supreme Court.")

    assert "at most 4 entities and 4 relations" in prompt
    assert "descriptions" in prompt
    assert GRAPH_EXTRACTION_SCHEMA["properties"]["entities"]["maxItems"] == 4
    assert GRAPH_EXTRACTION_SCHEMA["properties"]["relations"]["maxItems"] == 4
    assert (
        GRAPH_EXTRACTION_SCHEMA["properties"]["entities"]["items"][
            "additionalProperties"
        ]
        is False
    )


def test_graph_extraction_sends_compact_json_schema(monkeypatch):
    payloads = []

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"response": '{"entities":[],"relations":[]}'}

    def post(_url, *, json, timeout):
        payloads.append((json, timeout))
        return Response()

    monkeypatch.setattr("backend.app.services.llm_client.httpx.post", post)
    llm = graph_extraction_llm(
        {
            "OLLAMA_BASE_URL": "http://ollama.test",
            "GRAPH_LLM_MODEL": "smollm2:135m",
            "GRAPH_LLM_TIMEOUT_SECONDS": "60",
            "GRAPH_LLM_NUM_PREDICT": 700,
            "GRAPH_LLM_NUM_CTX": 4096,
        }
    )

    llm.generate("extract a graph")

    assert payloads[0][0]["format"] == GRAPH_EXTRACTION_SCHEMA
    assert payloads[0][0]["options"] == {
        "temperature": 0,
        "num_predict": 700,
        "num_ctx": 4096,
    }
