"""Credential-owner-authorized, all-configured-store Stage A inventory."""

import hashlib
import json
from collections import Counter
from datetime import UTC, datetime

import httpx

from backend.inventory.report import (
    application_report,
    scan,
    source_report,
    vector_status,
)
from backend.inventory.sql import connection_id, identifier, open_reader

SOURCE_MAPPING = {
    "table_name": "pdfs", "id_column": "path", "text_column": "ocr_text",
    "status_column": "ocr_status", "status_value": "done", "url_column": "url",
}


def timestamp():
    return datetime.now(UTC).isoformat()


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def failed(exc):
    return {"state": "blocked", "error_type": type(exc).__name__}


def source_inventory(env):
    url = env.get("OCR_TURSO_DB", "")
    with open_reader(url, env.get("OCR_TURSO_DB_TOKEN", "")) as reader:
        watermark = "SELECT count(*) AS records, max(updated_at) AS latest_updated_at FROM pdfs"
        before = reader.query(watermark)[0]
        report = source_report(reader, SOURCE_MAPPING)
        if report["state"] != "measured":
            return report, {}, None
        report["connection_id"] = connection_id(url)
        report["watermark_before"] = before
        report["coverage_by_status"] = reader.query(
            "SELECT ocr_status, count(*) AS records, "
            "sum(CASE WHEN ocr_text IS NOT NULL AND length(trim(ocr_text)) > 0 THEN 1 ELSE 0 END) AS nonempty_text, "
            "sum(CASE WHEN page_count IS NOT NULL THEN 1 ELSE 0 END) AS with_page_count "
            "FROM pdfs GROUP BY ocr_status ORDER BY ocr_status"
        )
        report["metadata_coverage"] = reader.query(
            "SELECT count(*) AS records, count(url) AS with_url, count(etag) AS with_etag, "
            "count(last_modified) AS with_last_modified, count(page_count) AS with_page_count FROM pdfs"
        )[0]
        records = {}
        manifests = []
        probe_text = None
        scanned_nonempty = 0
        scanned_statuses = Counter()
        for row in scan(reader, "SELECT path, ocr_text, ocr_status, updated_at FROM pdfs ORDER BY path", batch_size=10):
            text = row["ocr_text"]
            nonempty = isinstance(text, str) and bool(text.strip())
            scanned_nonempty += nonempty
            scanned_statuses[row["ocr_status"]] += 1
            eligible = row["ocr_status"] == "done" and nonempty and bool(row["path"])
            manifest = {"source_id_sha256": digest(row["path"] or ""),
                        "content_sha256": digest(text) if isinstance(text, str) else None,
                        "characters": len(text) if isinstance(text, str) else 0,
                        "status": row["ocr_status"], "eligible_text": eligible,
                        "updated_at": row["updated_at"]}
            manifests.append(manifest)
            records[row["path"]] = manifest
            if eligible and probe_text is None:
                probe_text = text[:1000]
        report["manifest"] = manifests
        report["manifest_sha256"] = digest(json.dumps(manifests, sort_keys=True))
        report["watermark_after"] = reader.query(watermark)[0]
        report["watermarks_match"] = report["watermark_before"] == report["watermark_after"]
        report["counts_reconciled"] = (
            len(manifests) == report["counts"]["total"] == before["records"] == report["watermark_after"]["records"]
            and len(set(records) - {None}) == report["counts"]["distinct_ids"]
            and scanned_nonempty == (report["counts"]["nonempty_text"] or 0)
            and scanned_statuses == Counter({row["ocr_status"]: row["records"] for row in report["coverage_by_status"]})
        )
        report["queries"] = reader.queries
        report["selector"] = (
            "SELECT path FROM pdfs WHERE ocr_status = 'done' AND ocr_text IS NOT NULL "
            "AND length(trim(ocr_text)) > 0 AND path IS NOT NULL ORDER BY path"
        )
        report["classification"] = {
            "unit": "source_document_not_chunk_vector",
            "safe_to_copy_vectors": 0,
            "requires_initial_chunking_and_embedding": sum(r["eligible_text"] for r in manifests),
            "requires_text_provenance_repair": sum(not r["eligible_text"] for r in manifests),
            "unknown_blocked": 0,
            "note": "Usable text is not a quality certification. Exclude non-done/empty text; preserve all source rows. "
                    "No existing OCR is repeated by this inventory.",
        }
        return report, records, probe_text


def app_inventory(env, source_records):
    url = env.get("TURSO_DATABASE_URL") or env.get("TURSO_CONNECTION_URL", "")
    with open_reader(url, env.get("TURSO_AUTH_TOKEN", "")) as reader:
        schema = reader.schema()
        counts = {table: reader.query(f"SELECT count(*) AS records FROM {identifier(table)}")[0]["records"]
                  for table in schema}
        report = {"state": "measured", "connection_id": connection_id(url),
                  "schema": schema, "table_counts": counts, "projects": []}
        projects = reader.query("SELECT id, organization_id FROM projects ORDER BY id")
        for project in projects:
            measured = application_report(reader, project["organization_id"], project["id"])
            measured.pop("schema", None)
            report["projects"].append({"scope": project, **measured})
        docs = reader.query(
            "SELECT id, organization_id, project_id, file_name, status, updated_at FROM documents ORDER BY id"
        )
        scopes = {(p["organization_id"], p["id"]) for p in projects}
        manifest = []
        for row in docs:
            matched = source_records.get(row["file_name"])
            manifest.append({"id": row["id"], "organization_id": row["organization_id"],
                             "project_id": row["project_id"], "status": row["status"],
                             "updated_at": row["updated_at"],
                             "filename_sha256": digest(row["file_name"] or ""),
                             "exact_source_path_match": matched is not None,
                             "source_content_sha256": matched["content_sha256"] if matched else None,
                             "source_eligible_text": matched["eligible_text"] if matched else None})
        report["documents"] = manifest
        report["document_statuses"] = dict(Counter(row["status"] for row in docs))
        matched_counts = Counter(row["file_name"] for row in docs if row["file_name"] in source_records)
        report["reconciliation"] = {
            "application_documents": len(docs), "exact_source_path_matches": sum(matched_counts.values()),
            "distinct_source_paths_matched": len(matched_counts),
            "repeated_source_path_groups": sum(count > 1 for count in matched_counts.values()),
            "extra_application_rows_for_repeated_source_paths": sum(count - 1 for count in matched_counts.values()),
            "unmatched_application_documents": len(docs) - sum(matched_counts.values()),
            "matched_documents_with_eligible_source_text": sum(r["source_eligible_text"] is True for r in manifest),
            "documents_with_missing_project_scope": sum((r["organization_id"], r["project_id"]) not in scopes for r in docs),
            "identity_caveat": "Filename equality is candidate reconciliation, not durable source identity or permission "
                               "to merge/delete. Unmatched uploads may be valid documents. Preserve all records.",
        }
        report["sources"] = []
        for row in reader.query(
            "SELECT id, organization_id, source_type, prefix, endpoint_url, updated_at FROM data_sources ORDER BY id"
        ):
            mapping = json.loads(row["prefix"] or "{}") if row["source_type"] == "turso_ocr" else {}
            report["sources"].append({
                "id": row["id"], "organization_id": row["organization_id"], "source_type": row["source_type"],
                "updated_at": row["updated_at"], "connection_id": connection_id(row["endpoint_url"] or ""),
                "same_connection_identifier_as_env_source": row["endpoint_url"] == env.get("OCR_TURSO_DB"),
                "mapped_project_exists_in_organization": (row["organization_id"], mapping.get("project_id")) in scopes,
                "mapping_and_state": {key: mapping.get(key) for key in (
                    "project_id", "table_name", "id_column", "text_column", "status_column", "status_value",
                    "url_column", "ingestion_status", "processed_count", "completed_count", "failed_count")},
            })
        report["document_watermark"] = reader.query(
            "SELECT count(*) AS records, max(updated_at) AS latest_updated_at FROM documents"
        )[0]
        report["source_configuration_integrity"] = {
            "records": len(report["sources"]),
            "mapped_project_missing_or_foreign": sum(not s["mapped_project_exists_in_organization"] for s in report["sources"]),
            "ingestion_statuses": dict(Counter(s["mapping_and_state"]["ingestion_status"] for s in report["sources"])),
            "note": "Stored running flags are historical metadata, not proof of a live worker. No cursor/status repaired.",
        }
        report["queries"] = reader.queries
        report["global_vector_integrity"] = reader.query(
            "SELECT count(*) AS total, "
            "coalesce(sum(CASE WHEN d.id IS NULL THEN 1 ELSE 0 END), 0) AS unresolved_document, "
            "coalesce(sum(CASE WHEN p.id IS NULL THEN 1 ELSE 0 END), 0) AS unresolved_project "
            "FROM chunk_embeddings c LEFT JOIN documents d ON d.id = c.document_id "
            "AND d.organization_id = c.organization_id AND d.project_id = c.project_id "
            "LEFT JOIN projects p ON p.id = c.project_id AND p.organization_id = c.organization_id"
        )[0]
        report["retrieval_coverage"] = {
            "documents": len(docs),
            "documents_with_stored_vectors": reader.query("SELECT count(DISTINCT document_id) AS count FROM chunk_embeddings")[0]["count"],
            "canonical_chunk_store": "legacy chunk_embeddings; no separate canonical chunk table discovered",
            "expected_chunk_count": None,
            "note": "Before canonical chunking, expected/missing chunk count is not measurable; zero rows is not indexing coverage. "
                    "Legacy ready status is not vector or GraphRAG readiness.",
        }
        return report


def graph_inventory(env):
    from neo4j import READ_ACCESS, GraphDatabase, unit_of_work

    queries = {
        "server": "CALL dbms.components() YIELD name, versions, edition RETURN name, versions, edition",
        "database": "CALL db.info() YIELD name RETURN name",
        "nodes": "MATCH (n) RETURN count(n) AS count",
        "edges": "MATCH ()-[r]->() RETURN count(r) AS count",
        "labels": "MATCH (n) UNWIND labels(n) AS label RETURN label, count(*) AS count",
        "relationship_types": "MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS count",
        "properties": "MATCH (n) UNWIND keys(n) AS property RETURN property, count(*) AS count",
        "indexes": "SHOW INDEXES YIELD * RETURN *",
        "constraints": "SHOW CONSTRAINTS YIELD * RETURN *",
    }
    report = {"state": "measured", "connection_id": connection_id(env.get("NEO4J_URI", "")),
              "scope": "entire configured default database, explicitly authorized by --all-configured", "queries": queries}
    with (
        GraphDatabase.driver(env["NEO4J_URI"], auth=(env["NEO4J_USERNAME"], env["NEO4J_PASSWORD"]),
                             connection_timeout=10, connection_acquisition_timeout=15,
                             max_transaction_retry_time=0) as driver,
        driver.session(default_access_mode=READ_ACCESS) as session,
    ):
        for name, query in queries.items():
            report[name] = session.execute_read(unit_of_work(timeout=30)(lambda tx, q=query: [dict(r) for r in tx.run(q)]))
    if report["nodes"][0]["count"] == 0 and report["edges"][0]["count"] == 0:
        report["coverage"] = {
            "state": "verified_empty_database_not_ready", "chunk_vectors": {"valid": 0, "total": 0},
            "entity_vectors": {"valid": 0, "total": 0}, "assertions_with_valid_chunk_document_evidence": {"valid": 0, "total": 0},
            "chunks_with_source_documents": {"valid": 0, "total": 0},
            "dimensions": {}, "model_generations": {}, "dangling_source_references": 0,
            "duplicate_records": 0, "vector_indexes": sum(i["type"] == "VECTOR" for i in report["indexes"]),
            "note": "Zero denominators mean no records, not 100% coverage or retrieval readiness. "
                    "Graph labels/provenance mapping must be defined and verified after writes in later stages.",
        }
    else:
        report["coverage"] = {"state": "blocked", "reason": "Nonempty graph requires deployed topology-specific coverage review"}
    return report


def model_inventory(env, probe_text):
    base = env.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model = env.get("OLLAMA_EMBEDDING_MODEL", "embeddinggemma")
    with httpx.Client(timeout=60, follow_redirects=False) as client:
        def tags():
            response = client.get(base + "/api/tags")
            response.raise_for_status()
            return response.json()["models"]

        def selected(models):
            return [m for m in models if m["name"] in (model, model + ":latest")]

        before = selected(tags())
        response = client.post(base + "/api/show", json={"model": model})
        response.raise_for_status()
        info = response.json()
        texts = ["Supreme Court semantic query compatibility probe."]
        if probe_text:
            texts.append(probe_text)
        response = client.post(base + "/api/embed", json={"model": model, "input": texts})
        response.raise_for_status()
        vectors = response.json()["embeddings"]
        after = selected(tags())
    measurements = [dict(zip(("state", "dimension"), vector_status(vector))) for vector in vectors]
    matching_digest = len(before) == len(after) == 1 and before[0]["digest"] == after[0]["digest"]
    valid = (len(vectors) == len(texts) and all(v["state"] == "valid_numeric" for v in measurements)
             and len({v["dimension"] for v in measurements}) == 1 and matching_digest)
    return {"state": "measured" if valid else "blocked", "connection_id": connection_id(base),
            "requested_model": model, "resolved_tag": before[0]["name"] if len(before) == 1 else None,
            "digest_before": before[0]["digest"] if len(before) == 1 else None,
            "digest_after": after[0]["digest"] if len(after) == 1 else None,
            "digest_stable_during_probe": matching_digest,
            "advertised_embedding_metadata": {key: value for key, value in info.get("model_info", {}).items()
                                               if "embedding_length" in key or key == "general.architecture"},
            "probes": measurements, "probe_text_sha256": [digest(text) for text in texts],
            "actual_source_excerpt_probed": bool(probe_text), "persisted_vectors": 0,
            "note": "Probe only: does not index the corpus. Pin/verify this digest for later ingestion/query generations."}


def measurement_issues(report):
    issues = [f"{name}_not_measured" for name in ("source", "application", "neo4j", "model")
              if report.get(name, {}).get("state") != "measured"]
    source = report.get("source", {})
    if source.get("watermarks_match") is not True or source.get("counts_reconciled") is not True:
        issues.append("source_counts_or_watermarks_inconsistent")
    if report.get("neo4j", {}).get("coverage", {}).get("state") != "verified_empty_database_not_ready":
        issues.append("graph_coverage_unverified")
    app = report.get("application", {})
    scanned = 0
    for project in app.get("projects", []):
        vectors = project.get("vectors", {})
        expected = project.get("tables", {}).get("chunk_embeddings", {}).get("count")
        counts = vectors.get("counts", {})
        measured = sum(counts.get(key, 0) for key in ("missing", "invalid", "valid_numeric"))
        classified = sum(vectors.get("classification", {}).values())
        scanned += measured
        if (project.get("blockers") or vectors.get("state") != "measured" or vectors.get("full_scan") is not True
                or expected != measured or classified != measured or vectors.get("stale_count") is None
                or vectors.get("generation_distribution") is None):
            issues.append("project_vector_coverage_unverified")
    if not (app.get("table_counts", {}).get("chunk_embeddings")
            == app.get("global_vector_integrity", {}).get("total") == scanned):
        issues.append("global_vectors_not_fully_scanned")
    if app.get("table_counts", {}).get("documents") != len(app.get("documents", [])):
        issues.append("application_document_counts_inconsistent")
    return issues


def inventory(env):
    report = {"started_at": timestamp(), "gate": "CLOSED_PENDING_USER_REVIEW",
              "review": {"reviewer": None, "date": None, "decision": "pending"},
              "scope": "All records in explicitly configured application/source Turso and Neo4j default database",
              "consistency": "No cross-store snapshot. Source watermarks checked; concurrent changes can invalidate eligibility.",
              "commands": [".venv/bin/python -m backend.scripts.inventory --env-file backend/.env --all-configured --output <new-report.json>"]}
    records, text = {}, None
    for name in ("source", "application", "neo4j", "model"):
        try:
            if name == "source":
                report[name], records, text = source_inventory(env)
            elif name == "application":
                report[name] = app_inventory(env, records)
            elif name == "neo4j":
                report[name] = graph_inventory(env)
            else:
                report[name] = model_inventory(env, text)
        except Exception as exc:  # noqa: BLE001 - secret-safe per-service diagnostic boundary
            report[name] = failed(exc)
    report["measurement_issues"] = measurement_issues(report)
    report["measurement_status"] = "incomplete" if report["measurement_issues"] else "complete"
    report["finished_at"] = timestamp()
    return report
