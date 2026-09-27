import hashlib
import json
import re

from ai.schemas.graph import GraphEntity, GraphRelation


def normalize_entity_name(name: str) -> str:
    value = name.strip().strip("'\"").lower()
    return re.sub(r"\s+", " ", value)


def entity_id(project_id: str, normalized_name: str) -> str:
    digest = hashlib.sha1(normalized_name.encode("utf-8")).hexdigest()[:16]
    return f"entity:{project_id}:{digest}"


def parse_graph_json(payload: str) -> tuple[list[GraphEntity], list[GraphRelation]]:
    data = json.loads(payload)
    entities = [
        GraphEntity(item["name"], normalize_entity_name(item["name"]), item.get("type"), item.get("description"))
        for item in data.get("entities", [])
        if item.get("name")
    ]
    relations = [
        GraphRelation(item["source"], item["target"], item["relation"], item.get("description"), float(item.get("weight", 1)))
        for item in data.get("relations", [])
        if item.get("source") and item.get("target") and item.get("relation")
    ]
    return entities, relations
