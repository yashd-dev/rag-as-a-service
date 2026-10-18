"""Full-scan legacy corpus measurements; no assumptions of migration eligibility."""

import json
import math
from collections import Counter

from backend.inventory.sql import identifier


def vector_status(value):
    if value is None:
        return "missing", None
    try:
        vector = json.loads(value) if isinstance(value, str) else value
        if not isinstance(vector, (list, tuple)) or not vector:
            return "invalid", None
        if any(
            isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
            for v in vector
        ):
            return "invalid", len(vector)
        if not any(v != 0 for v in vector):
            return "invalid", len(vector)
        return "valid_numeric", len(vector)
    except (ValueError, TypeError, OverflowError):
        return "invalid", None


def columns(schema, table):
    return {column["name"] for column in schema.get(table, [])}


def scan(reader, statement, parameters=(), batch_size=500):
    offset = 0
    while True:
        rows = reader.query(statement + " LIMIT ? OFFSET ?", (*parameters, batch_size, offset))
        yield from rows
        if len(rows) < batch_size:
            return
        offset += len(rows)


def application_report(reader, org, project):
    schema = reader.schema()
    report = {
        "schema": schema,
        "sqlite_version": reader.query("SELECT sqlite_version() AS version")[0]["version"],
        "tables": {},
        "blockers": [],
    }
    for table in ("projects", "documents", "chunk_embeddings"):
        required = {"organization_id", "id" if table == "projects" else "project_id"}
        if table not in schema:
            report["tables"][table] = {"state": "missing_schema"}
            report["blockers"].append(f"Missing application table: {table}")
            continue
        if not required <= columns(schema, table):
            report["tables"][table] = {"state": "unrecognized_scope_schema"}
            report["blockers"].append(f"Unrecognized scope columns: {table}")
            continue
        project_key = "id" if table == "projects" else "project_id"
        where = f"organization_id = ? AND {project_key} = ?"
        result = reader.query(
            f"SELECT count(*) AS count FROM {identifier(table)} WHERE {where}", (org, project)
        )[0]
        report["tables"][table] = {"state": "measured", **result}
    if report["tables"].get("projects", {}).get("count") != 1:
        report["blockers"].append("Scope must resolve to exactly one application project")
    if {"embedding_provider", "embedding_model"} <= columns(schema, "projects"):
        report["project_model_labels_not_vector_provenance"] = reader.query(
            "SELECT embedding_provider, embedding_model FROM projects "
            "WHERE organization_id = ? AND id = ?", (org, project)
        )
    required = {"id", "content", "embedding", "document_id", "organization_id", "project_id"}
    if not required <= columns(schema, "chunk_embeddings"):
        report["blockers"].append("Cannot scan stored vectors: missing required columns")
        return report
    stats = Counter()
    dimensions = Counter()
    eligibility = Counter({"safe_to_copy": 0, "requires_reembedding": 0,
                           "requires_text_provenance_repair": 0, "unknown_blocked": 0})
    # Use the database's supported vector decoder, never guess a BLOB encoding.
    statement = (
        "SELECT id, document_id, content, vector_extract(embedding) AS vector "
        "FROM chunk_embeddings WHERE organization_id = ? AND project_id = ? ORDER BY id"
    )
    can_resolve_documents = {"id", "organization_id", "project_id"} <= columns(schema, "documents")
    document_ids = set()
    if can_resolve_documents:
        document_ids = {row["id"] for row in scan(
            reader, "SELECT id FROM documents WHERE organization_id = ? AND project_id = ? ORDER BY id",
            (org, project),
        )}
    try:
        for row in scan(reader, statement, (org, project)):
            state, dimension = vector_status(row["vector"])
            stats[state] += 1
            if dimension is not None:
                dimensions[str(dimension)] += 1
            has_text = isinstance(row["content"], str) and bool(row["content"].strip())
            linked = can_resolve_documents and row["document_id"] in document_ids
            stats["nonempty_text"] += int(has_text)
            stats["resolved_document"] += int(linked)
            if not has_text or not linked:
                eligibility["requires_text_provenance_repair"] += 1
            elif state != "valid_numeric":
                eligibility["requires_reembedding"] += 1
            else:
                # Legacy rows have no per-vector model, revision or content hash.
                eligibility["unknown_blocked"] += 1
        report["vectors"] = {
            "state": "measured", "full_scan": True, "counts": dict(stats),
            "dimensions": dict(dimensions), "classification": dict(eligibility),
            "selector": {"organization_id": org, "project_id": project,
                         "order_by": "chunk_embeddings.id"},
            "classification_rule": "Repair missing text/document first; re-embed missing/invalid vectors; "
                                   "all remaining legacy rows blocked by unverified model/content provenance.",
            "stale_count": None, "generation_distribution": None,
        }
    except Exception as exc:  # noqa: BLE001 - unknown driver errors must not leak secrets
        # Driver errors can contain URLs, tokens, SQL values or document content.
        report["vectors"] = {"state": "blocked", "error_type": type(exc).__name__}
    report["blockers"].append(
        "Per-vector model/revision/content-hash/generation and staleness are unverified; "
        "project labels cannot authorize copying"
    )
    return report


def source_report(reader, mapping):
    schema = reader.schema()
    table = mapping.get("table_name")
    required = {mapping.get("id_column"), mapping.get("text_column")}
    status = mapping.get("status_column")
    if status:
        required.add(status)
    result = {"schema": schema, "mapping": {k: mapping.get(k) for k in (
        "table_name", "id_column", "text_column", "status_column", "url_column")}}
    if table not in schema or None in required or not required <= columns(schema, table):
        return {**result, "state": "mapping_not_verified"}
    name = identifier(table)
    text = identifier(mapping["text_column"])
    source_id = identifier(mapping["id_column"])
    result["sqlite_version"] = reader.query("SELECT sqlite_version() AS version")[0]["version"]
    result["counts"] = reader.query(
        f"SELECT count(*) AS total, count(DISTINCT {source_id}) AS distinct_ids, "
        f"sum(CASE WHEN {source_id} IS NULL THEN 1 ELSE 0 END) AS null_ids, "
        f"sum(CASE WHEN {text} IS NOT NULL AND length(trim({text})) > 0 THEN 1 ELSE 0 END) AS nonempty_text "
        f"FROM {name}"
    )[0]
    where = f"{identifier(status)} = ?" if status else "1 = 1"
    parameters = (mapping.get("status_value"),) if status else ()
    result["eligible_ocr_counts"] = reader.query(
        f"SELECT count(*) AS rows, "
        f"sum(CASE WHEN {text} IS NOT NULL AND length(trim({text})) > 0 THEN 1 ELSE 0 END) AS nonempty_text "
        f"FROM {name} WHERE {where}", parameters
    )[0]
    result["state"] = "measured"
    result["scope_caveat"] = "Counts cover the configured source table, not proven project ownership of each row."
    result["source_application_identity_reconciliation"] = "unknown: legacy filename is not a durable source mapping"
    return result
