"""Run with python -m backend.scripts.inventory; never imports backend.app."""

import argparse
import hashlib
import json
import os
from base64 import urlsafe_b64encode
from datetime import UTC, datetime
from pathlib import Path

from backend.inventory.graph import graph_report
from backend.inventory.report import application_report, columns, source_report
from backend.inventory.sql import blocked, connection_id, open_reader


def now():
    return datetime.now(UTC).isoformat()


def source_inventory(reader, schema, org, project, source_id, env):
    required = {"id", "organization_id", "source_type", "prefix", "endpoint_url",
                "encrypted_secret_access_key"}
    if not required <= columns(schema, "data_sources"):
        return {"state": "missing_source_schema"}
    rows = reader.query(
        "SELECT id, prefix, endpoint_url, encrypted_secret_access_key FROM data_sources "
        "WHERE organization_id = ? AND source_type = ? AND id = ?",
        (org, "turso_ocr", source_id),
    )
    if len(rows) != 1:
        return {"state": "source_not_found_in_scope"}
    row = rows[0]
    mapping = json.loads(row["prefix"] or "{}")
    if mapping.get("project_id") != project:
        return {"state": "source_project_mismatch"}
    # Same documented encryption format as SecretBox, without importing app.
    from cryptography.fernet import Fernet

    key = env.get("CREDENTIAL_ENCRYPTION_KEY", "")
    if not key:
        return {"state": "missing_encryption_key"}
    fernet = Fernet(urlsafe_b64encode(hashlib.sha256(key.encode()).digest()))
    token = fernet.decrypt(row["encrypted_secret_access_key"].encode()).decode()
    with open_reader(row["endpoint_url"], token) as source:
        result = source_report(source, mapping)
        result["connection_id"] = connection_id(row["endpoint_url"])
        result["queries"] = source.queries
        return result


def build_report(args, env):
    if getattr(args, "all_configured", False):
        from backend.inventory.live import inventory

        return inventory(env)
    result = {
        "started_at": now(), "scope": {"organization_id": args.organization_id,
                                       "project_id": args.project_id, "source_id": args.source_id},
        "gate": "CLOSED", "review": "pending user review",
        "consistency": "Independent read statements, no cross-store snapshot; concurrent changes may affect counts. "
                       "Refresh inventory before migration; no eligibility granted by this diagnostic.",
    }
    url = env.get("TURSO_DATABASE_URL") or env.get("TURSO_CONNECTION_URL", "")
    result["application_connection_id"] = connection_id(url)
    try:
        with open_reader(url, env.get("TURSO_AUTH_TOKEN", "")) as reader:
            if args.discover_scopes:
                schema = reader.schema()
                result["discovery"] = {}
                for table, fields in (("projects", {"id", "organization_id"}),
                                      ("data_sources", {"id", "organization_id", "source_type"})):
                    if fields <= columns(schema, table):
                        # Discovery is explicit and emits identity metadata only.
                        result["discovery"][table] = reader.query(
                            f"SELECT {', '.join(sorted(fields))} FROM {table} ORDER BY id"
                        )
                    else:
                        result["discovery"][table] = {"state": "missing_schema"}
            else:
                result["application"] = application_report(reader, args.organization_id, args.project_id)
                if args.source_id:
                    try:
                        result["source"] = source_inventory(
                            reader, result["application"]["schema"], args.organization_id,
                            args.project_id, args.source_id, env,
                        )
                    except Exception as exc:  # noqa: BLE001 - secret-safe diagnostic boundary
                        result["source"] = blocked(exc)
                else:
                    result["source"] = {"state": "blocked", "reason": "Explicit --source-id required"}
            result["application_queries"] = reader.queries
    except Exception as exc:  # noqa: BLE001 - secret-safe diagnostic boundary
        result["application"] = blocked(exc)
    if not args.discover_scopes:
        if all(env.get(key) for key in ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD")):
            try:
                result["neo4j"] = graph_report(
                    env["NEO4J_URI"], env["NEO4J_USERNAME"], env["NEO4J_PASSWORD"],
                    args.organization_id, args.project_id,
                )
                result["neo4j"]["connection_id"] = connection_id(env["NEO4J_URI"])
            except Exception as exc:  # noqa: BLE001 - secret-safe diagnostic boundary
                result["neo4j"] = blocked(exc)
        else:
            result["neo4j"] = {"state": "blocked", "reason": "Explicit Neo4j configuration required"}
        result["model_probe"] = {"state": "not_requested"}
        if args.probe_model:
            try:
                import httpx

                from backend.inventory.report import vector_status

                base = env.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
                model = env.get("OLLAMA_EMBEDDING_MODEL", "embeddinggemma")
                with httpx.Client(timeout=30, follow_redirects=False) as client:
                    response = client.post(base + "/api/embed", json={
                        "model": model, "input": "Read-only embedding dimension compatibility probe.",
                    })
                    response.raise_for_status()
                    payload = response.json()
                    state, dimension = vector_status(payload["embeddings"][0])
                result["model_probe"] = {"state": state, "dimension": dimension,
                                         "requested_model": model, "revision": "unverified",
                                         "connection_id": connection_id(base), "persisted": False}
            except Exception as exc:  # noqa: BLE001 - secret-safe diagnostic boundary
                result["model_probe"] = blocked(exc)
    result["finished_at"] = now()
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, help="Explicit dotenv file; defined values override process environment, matching backend Config")
    parser.add_argument("--organization-id")
    parser.add_argument("--project-id")
    parser.add_argument("--source-id")
    parser.add_argument("--discover-scopes", action="store_true", help="Read identity metadata only; no inventory")
    parser.add_argument("--all-configured", action="store_true", help="Explicitly authorize inventory of all configured database records and source OCR env connection")
    parser.add_argument("--probe-model", action="store_true", help="Transient Ollama embed request; never stores vectors")
    parser.add_argument("--output", type=Path, required=True, help="New JSON report path; refuses overwrite")
    args = parser.parse_args(argv)
    if not args.discover_scopes and not args.all_configured and not (args.organization_id and args.project_id):
        parser.error("--organization-id and --project-id required unless discovering scopes")
    if args.discover_scopes and (args.organization_id or args.project_id or args.source_id or args.probe_model):
        parser.error("Discovery cannot be combined with scoped inventory or model probes")
    if args.all_configured and (args.discover_scopes or args.organization_id or args.project_id or args.source_id or args.probe_model):
        parser.error("--all-configured cannot be combined with discovery, scope or probe flags; it includes model probing")
    env = dict(os.environ)
    if args.env_file:
        from dotenv import dotenv_values
        env.update({key: value for key, value in dotenv_values(args.env_file).items() if value is not None})
    # Reserve a new report before any connections; never truncate prior evidence.
    with args.output.open("x", encoding="utf-8") as output:
        report = build_report(args, env)
        json.dump(report, output, indent=2, default=str, allow_nan=False)
        output.write("\n")
    print(f"Read-only report: {args.output}; migration gate CLOSED")
    return 2  # Inventory/review is deliberately not certified by tool success.


if __name__ == "__main__":
    raise SystemExit(main())
