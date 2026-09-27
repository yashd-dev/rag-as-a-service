from dataclasses import dataclass


@dataclass(frozen=True)
class GraphEntity:
    name: str
    normalized_name: str
    entity_type: str | None = None
    description: str | None = None


@dataclass(frozen=True)
class GraphRelation:
    source: str
    target: str
    relation: str
    description: str | None = None
    weight: float = 1.0
