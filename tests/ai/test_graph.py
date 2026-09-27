from ai.graph.extractor import entity_id, normalize_entity_name, parse_graph_json


def test_normalize_entity_name():
    assert normalize_entity_name("  'Supreme   Court'  ") == "supreme court"


def test_entity_id_is_stable():
    assert entity_id("p1", "article 21") == entity_id("p1", "article 21")


def test_parse_graph_json():
    entities, relations = parse_graph_json('{"entities":[{"name":"Article 21","type":"law"}],"relations":[{"source":"Court","target":"Article 21","relation":"interprets"}]}')

    assert entities[0].normalized_name == "article 21"
    assert relations[0].relation == "interprets"
