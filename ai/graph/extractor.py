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
    data = json.loads(extract_json_object(payload))
    entities = []
    for item in data.get("entities", []):
        name = item.get("name") or item.get("entity")
        if name and not is_placeholder(name):
            entities.append(GraphEntity(name, normalize_entity_name(name), item.get("type") or item.get("entity_type") or "entity", item.get("description")))

    relations = []
    for item in data.get("relations", []):
        source = item.get("source") or item.get("source_entity")
        target = item.get("target") or item.get("target_entity")
        relation = item.get("relation") or item.get("relationship") or item.get("type")
        if source and target and relation and not is_placeholder(source) and not is_placeholder(target) and not is_placeholder(relation):
            relations.append(GraphRelation(source, target, relation, item.get("description"), float(item.get("weight", 1))))
    return entities, relations


def graph_json_stats(payload: str) -> dict:
    try:
        data = json.loads(extract_json_object(payload))
    except json.JSONDecodeError:
        return {"raw_entities": 0, "raw_relations": 0, "placeholder_entities": 0, "placeholder_relations": 0}
    raw_entities = data.get("entities", []) if isinstance(data.get("entities"), list) else []
    raw_relations = data.get("relations", []) if isinstance(data.get("relations"), list) else []
    placeholder_entities = sum(1 for item in raw_entities if is_placeholder(item.get("name") or item.get("entity")))
    placeholder_relations = sum(
        1
        for item in raw_relations
        if is_placeholder(item.get("source") or item.get("source_entity"))
        or is_placeholder(item.get("target") or item.get("target_entity"))
        or is_placeholder(item.get("relation") or item.get("relationship") or item.get("type"))
    )
    return {
        "raw_entities": len(raw_entities),
        "raw_relations": len(raw_relations),
        "placeholder_entities": placeholder_entities,
        "placeholder_relations": placeholder_relations,
    }


def is_placeholder(value: str | None) -> bool:
    if not value:
        return True
    normalized = normalize_entity_name(value)
    return normalized in {"...", "entity name", "person name", "source", "target", "relation", "entity"}


def extract_json_object(payload: str) -> str:
    value = payload.strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value, flags=re.IGNORECASE).strip()
        value = re.sub(r"\s*```$", "", value).strip()
    start = value.find("{")
    if start == -1:
        return value
    depth = 0
    in_string = False
    escape = False
    for index, char in enumerate(value[start:], start=start):
        if escape:
            escape = False
            continue
        if char == "\\" and in_string:
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return value[start : index + 1]
    return value[start:]


def graph_extraction_prompt(text: str) -> str:
    return f"""
Extract a small knowledge graph from the legal text.
Return only the JSON object required by the supplied schema.
Use only real names that appear in the text.
Do not output placeholders, markdown, commentary, descriptions, or weights.
Return at most 4 entities and 4 relations.
Entity fields: name, type.
Relation fields: source, target, relation.
Relation source and target must exactly match returned entity names.
If none are found, return empty arrays.

Text:
{text}
""".strip()


def extract_fallback_entities(text: str, limit: int = 25) -> list[GraphEntity]:
    candidates: list[str] = []
    patterns = [
        r"\b[A-Z][A-Za-z0-9]*(?:\s+[A-Z][A-Za-z0-9]*){1,5}\b",
        r"\b[A-Z]{2,}\b",
    ]
    for pattern in patterns:
        candidates.extend(re.findall(pattern, text))
    stopwords = {
        "Abstract",
        "Introduction",
        "Conclusion",
        "References",
        "Figure",
        "Table",
        "The",
        "This",
        "These",
        "That",
        "Based",
    }
    entities = []
    seen = set()
    for candidate in candidates:
        name = re.sub(r"\s+", " ", candidate).strip()
        if name in stopwords or len(name) < 3:
            continue
        normalized = normalize_entity_name(name)
        if normalized in seen:
            continue
        seen.add(normalized)
        entities.append(GraphEntity(name=name, normalized_name=normalized, entity_type="term", description="Extracted by fallback entity matcher"))
        if len(entities) >= limit:
            break
    return entities


def fallback_relations(entities: list[GraphEntity], limit: int = 30) -> list[GraphRelation]:
    relations = []
    for source, target in zip(entities, entities[1:], strict=False):
        relations.append(
            GraphRelation(
                source=source.name,
                target=target.name,
                relation="co_occurs_with",
                description="Fallback relation between nearby extracted terms",
                weight=1,
            )
        )
        if len(relations) >= limit:
            break
    return relations
