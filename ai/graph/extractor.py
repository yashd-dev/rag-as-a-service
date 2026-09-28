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
    entities = [
        GraphEntity(item["name"], normalize_entity_name(item["name"]), item.get("type") or item.get("entity_type"), item.get("description"))
        for item in data.get("entities", [])
        if item.get("name") and not is_placeholder(item.get("name"))
    ]
    relations = [
        GraphRelation(
            item.get("source") or item.get("source_entity"),
            item.get("target") or item.get("target_entity"),
            item.get("relation") or item.get("relationship") or item.get("type"),
            item.get("description"),
            float(item.get("weight", 1)),
        )
        for item in data.get("relations", [])
        if (item.get("source") or item.get("source_entity"))
        and (item.get("target") or item.get("target_entity"))
        and (item.get("relation") or item.get("relationship") or item.get("type"))
        and not is_placeholder(item.get("source") or item.get("source_entity"))
        and not is_placeholder(item.get("target") or item.get("target_entity"))
    ]
    return entities, relations


def is_placeholder(value: str | None) -> bool:
    if not value:
        return True
    normalized = normalize_entity_name(value)
    return normalized in {"...", "entity name", "source", "target"}


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
Extract a knowledge graph from the text.
Return JSON only. Do not summarize. Do not explain.
The JSON must have both keys: entities and relations.
Do not use placeholder values like "..." or "entity name".
Use this exact shape:
{{
  "entities": [{{"name": "...", "type": "...", "description": "..."}}],
  "relations": [{{"source": "entity name", "target": "entity name", "relation": "...", "description": "...", "weight": 1}}]
}}
If no relations are found, return "relations": [].

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
