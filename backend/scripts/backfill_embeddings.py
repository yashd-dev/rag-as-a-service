import argparse

from ai.graph.store import Neo4jGraphStore
from backend.app import create_app
from backend.app.db.repository import ProjectRepository
from backend.app.services.embedding_service import embedding_provider_for_project
from backend.app.services.vector_store import TursoVectorStore


def batches(items: list[dict], size: int):
    for offset in range(0, len(items), size):
        yield items[offset : offset + size]


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill Turso vectors from existing Neo4j chunks; safely resumes after interruption.")
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--organization-id", required=True)
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("--batch-size must be positive")

    app = create_app()
    config = app.config
    project = ProjectRepository(config["TURSO_DATABASE_URL"], config["TURSO_AUTH_TOKEN"]).get(
        args.project_id, args.organization_id
    )
    if not project:
        parser.error("Project not found for the supplied organization")

    graph = Neo4jGraphStore(config["NEO4J_URI"], config["NEO4J_USERNAME"], config["NEO4J_PASSWORD"])
    try:
        chunks = graph.project_chunks(args.project_id)
    finally:
        graph.close()
    store = TursoVectorStore(config["TURSO_DATABASE_URL"], config["TURSO_AUTH_TOKEN"])
    provider = embedding_provider_for_project(config, project)
    completed = skipped = 0
    for batch in batches(chunks, args.batch_size):
        existing = store.existing_ids(args.project_id, [chunk["id"] for chunk in batch])
        pending = [chunk for chunk in batch if chunk["id"] not in existing]
        skipped += len(batch) - len(pending)
        if not pending:
            continue
        vectors = provider.embed_texts([chunk["content"] for chunk in pending])
        store.upsert(project, pending, vectors)
        completed += len(pending)
        print(f"backfill project={args.project_id} embedded={completed} skipped={skipped}", flush=True)
    print(
        f"backfill complete project={args.project_id} embedded={completed} already_present={skipped} total={len(chunks)}",
        flush=True,
    )


if __name__ == "__main__":
    main()
