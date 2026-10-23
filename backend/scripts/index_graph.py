"""Plan/extract/review an evidence graph; default plan performs no model or Neo4j calls."""

import argparse
import json
import logging
import os
from pathlib import Path

from dotenv import dotenv_values

from backend.app.services.embedding_service import EmbeddingGemmaProvider
from backend.app.services.evidence_graph import EvidenceGraph
from backend.app.services.graph_extraction import graph_extractor_for_project
from backend.app.services.neo4j_vectors import Neo4jVectorStore, canonical_snapshot


def execute(args):
    config = dict(os.environ) | {
        key: value
        for key, value in dotenv_values(args.env_file).items()
        if value is not None
    }
    config["TURSO_DATABASE_URL"] = config.get("TURSO_DATABASE_URL") or config.get(
        "TURSO_CONNECTION_URL", ""
    )
    config.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")
    config.setdefault("GRAPH_LLM_MODEL", "smollm2:135m")
    config.setdefault("GRAPH_LLM_NUM_PREDICT", 700)
    if getattr(args, "strategy", None) is not None:
        config["GRAPH_EXTRACTION_STRATEGY"] = args.strategy
    if getattr(args, "model", None) is not None:
        config["GRAPH_LLM_MODEL"] = args.model
    snapshot = canonical_snapshot(
        config, {"id": args.project_id, "organization_id": args.organization_id}
    )
    summary = {
        "canonical_manifest": snapshot["manifest"],
        "expected_chunks": len(snapshot["rows"]),
        "documents": len({row["document_id"] for row in snapshot["rows"]}),
        "excluded_document_ids": snapshot["excluded_document_ids"],
        "strategy": config.get("GRAPH_EXTRACTION_STRATEGY", "full_legal"),
        "requested_model": config["GRAPH_LLM_MODEL"],
    }
    if not any((args.apply, args.query, args.status, args.publish, args.withdraw)):
        return summary | {
            "dry_run": True,
            "database_writes": False,
            "model_calls": False,
        }
    provider = EmbeddingGemmaProvider(
        config["OLLAMA_BASE_URL"],
        config.get("OLLAMA_EMBEDDING_MODEL", "embeddinggemma"),
    )
    vectors = Neo4jVectorStore(config, snapshot, provider.revision())
    try:
        extractor = graph_extractor_for_project(config, vectors.key)
        graph = EvidenceGraph(vectors, extractor.profile)
        graph.require_vectors()
        if args.apply:
            maximum = (
                args.max_chunks
                if args.max_chunks is not None
                else int(config.get("GRAPH_EXTRACTION_MAX_CHUNKS", 0))
            )
            result = graph.build(extractor, max_chunks=maximum)
        elif args.query:
            result = graph.search(provider, args.query, require_publication=False)
        elif args.publish:
            graph.publish()
            result = {"state": "graph_published", "graph_key": graph.key}
        elif args.withdraw:
            graph.withdraw()
            result = {"state": "graph_publication_withdrawn", "graph_key": graph.key}
        else:
            result = graph.integrity(complete=False)
        if (
            canonical_snapshot(
                config, {"id": args.project_id, "organization_id": args.organization_id}
            )
            != snapshot
        ):
            raise ValueError("Canonical generation changed during graph operation")
        if hasattr(extractor, "inference_calls"):
            result["citation_verifier_calls"] = extractor.inference_calls
        return summary | result | {"extractor": extractor.profile}
    finally:
        vectors.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path("backend/.env"))
    parser.add_argument("--organization-id", required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument(
        "--strategy",
        choices=["full_legal", "citation_candidates"],
        help="Process-local opt-in; default/config remains full_legal",
    )
    parser.add_argument(
        "--model",
        help="Process-local local graph model override; does not edit application settings",
    )
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument("--apply", action="store_true")
    operation.add_argument(
        "--query",
        help="Diagnostic semantic-seeded graph retrieval; no answer generation",
    )
    operation.add_argument("--status", action="store_true")
    operation.add_argument(
        "--publish",
        action="store_true",
        help="Only after reviewed live graph retrieval acceptance",
    )
    operation.add_argument("--withdraw", action="store_true")
    parser.add_argument(
        "--max-chunks",
        type=int,
        help="Cap NEW extraction attempts; 0 means all, failures retry on next run",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(message)s")
    logging.getLogger("backend.app.services.evidence_graph").setLevel(logging.INFO)
    try:
        result = execute(args)
    except Exception as exc:  # noqa: BLE001
        # The CLI boundary redacts transport credentials and source text.
        print(json.dumps({"state": "failed", "error_code": type(exc).__name__}))
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 2 if result.get("failures") or result.get("state") == "graph_partial" else 0


if __name__ == "__main__":
    raise SystemExit(main())
