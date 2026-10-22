"""Authorized canonical text resolution, including intact historical generations."""

import json

from backend.app.services.grounding import citation
from backend.app.services.rag import fingerprint
from backend.inventory.sql import open_reader


def resolve_passage(config, project, chunk_id):
    with open_reader(
        config["TURSO_DATABASE_URL"], config["TURSO_AUTH_TOKEN"]
    ) as reader:
        rows = reader.query(
            "SELECT c.*,g.document_id,g.source_text,g.source_metadata,g.recipe_json,g.content_hash AS document_content_hash,"
            "d.file_name,s.current_generation FROM canonical_chunks c JOIN index_generations g ON g.id=c.generation_id "
            "JOIN documents d ON d.id=g.document_id AND d.project_id=g.project_id AND d.organization_id=g.organization_id "
            "LEFT JOIN document_sources s ON s.document_id=d.id AND s.project_id=d.project_id AND s.organization_id=d.organization_id "
            "WHERE c.id=? AND g.project_id=? AND g.organization_id=? AND d.project_id=? AND d.organization_id=?",
            (
                chunk_id,
                project["id"],
                project["organization_id"],
                project["id"],
                project["organization_id"],
            ),
        )
    if not rows:
        return None
    if len(rows) != 1:
        raise ValueError("Ambiguous canonical source")
    row = rows[0]
    text, start, end = row["source_text"], row["start_char"], row["end_char"]
    metadata, recipe = json.loads(row["source_metadata"]), json.loads(
        row["recipe_json"]
    )
    if (
        type(start) is not int
        or type(end) is not int
        or not 0 <= start < end <= len(text)
        or text[start:end] != row["content"]
        or fingerprint(row["content"]) != row["content_hash"]
        or fingerprint(text) != row["document_content_hash"]
        or row["id"]
        != "chk_"
        + fingerprint([row["generation_id"], row["chunk_index"], row["content"]])
        or row["generation_id"]
        != "gen_" + fingerprint([row["document_id"], text, metadata, recipe])
        or json.loads(row["source_pages"])
        != [
            page
            for page in metadata.get("pages", [])
            if page["start"] < end and page["end"] > start
        ]
    ):
        raise ValueError("Canonical source integrity failed")
    result = citation(
        project,
        {
            "chunk": row,
            "vector_score": None,
            "fusion_score": None,
            "methods": [],
            "path": [],
        },
        None,
    )
    return result | {
        "content": row["content"],
        "chunk_index": row["chunk_index"],
        "is_current_generation": row["current_generation"] == row["generation_id"],
    }
