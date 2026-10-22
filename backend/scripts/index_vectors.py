"""Plan/build/review a canonical Neo4j vector generation; default is read-only."""

import argparse
import json
import logging
import os
from pathlib import Path

from dotenv import dotenv_values

from backend.app.services.embedding_service import EmbeddingGemmaProvider
from backend.app.services.neo4j_vectors import Neo4jVectorStore, canonical_snapshot
from backend.inventory.sql import open_reader


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path("backend/.env"))
    parser.add_argument("--organization-id", required=True)
    parser.add_argument("--project-id", required=True)
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument(
        "--apply",
        action="store_true",
        help="Embed canonical text; leave generation unpublished",
    )
    operation.add_argument(
        "--query",
        help="Read-only candidate retrieval for passage review; no answer generation",
    )
    operation.add_argument(
        "--publish",
        action="store_true",
        help="Publish only after operator-reviewed retrieval and rollback checks",
    )
    operation.add_argument(
        "--withdraw",
        action="store_true",
        help="Revoke publication, retaining all vectors/input",
    )
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--limit", type=int, default=8)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(message)s")
    logging.getLogger("backend.app.services.neo4j_vectors").setLevel(logging.INFO)
    config = dict(os.environ) | {
        k: v for k, v in dotenv_values(args.env_file).items() if v is not None
    }
    config["TURSO_DATABASE_URL"] = config.get("TURSO_DATABASE_URL") or config.get(
        "TURSO_CONNECTION_URL", ""
    )
    with open_reader(
        config["TURSO_DATABASE_URL"], config["TURSO_AUTH_TOKEN"]
    ) as reader:
        projects = reader.query(
            "SELECT * FROM projects WHERE id=? AND organization_id=?",
            (args.project_id, args.organization_id),
        )
    if not projects:
        parser.error("Project not found in organization")
    project = projects[0]
    snapshot = canonical_snapshot(config, project)
    summary = {
        "manifest": snapshot["manifest"],
        "expected_chunks": len(snapshot["rows"]),
        "documents": len({row["document_id"] for row in snapshot["rows"]}),
        "excluded_document_ids": snapshot["excluded_document_ids"],
        "scope": "current_canonical_generations",
    }
    if not any((args.apply, args.query, args.publish, args.withdraw)):
        print(
            json.dumps(
                summary
                | {"dry_run": True, "model_probe": False, "database_writes": False}
            )
        )
        return 0
    provider = EmbeddingGemmaProvider(
        config.get("OLLAMA_BASE_URL", "http://localhost:11434"),
        config.get("OLLAMA_EMBEDDING_MODEL", "embeddinggemma"),
    )
    provenance = provider.resolve()
    store = Neo4jVectorStore(config, snapshot, provenance)
    try:
        result = summary | {"partition": store.key, "provenance": provenance}
        if args.apply:
            result.update(store.build(provider, args.batch_size))
        elif args.query:
            result.update(
                results=store.search(
                    provider, args.query, args.limit, require_publication=False
                ),
                mode="vector",
                path="neo4j_partitioned_vector_index",
                review_status="pending",
            )
        elif args.withdraw:
            store.withdraw()
            result["state"] = "publication_withdrawn"
        else:
            if (
                canonical_snapshot(config, project) != snapshot
                or provider.revision() != provenance
            ):
                raise ValueError("Canonical input or model changed before publication")
            store.publish()
            result["state"] = "vector_ready"
        if canonical_snapshot(config, project) != snapshot:
            raise ValueError("Canonical input changed during operation")
        print(json.dumps(result))
        return 0
    except (
        Exception
    ) as exc:  # noqa: BLE001 - CLI boundary emits secret-safe failure codes
        # Do not emit driver messages, connection strings, source text or credentials on failure.
        print(
            json.dumps(summary | {"state": "failed", "error_code": type(exc).__name__})
        )
        return 2
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
