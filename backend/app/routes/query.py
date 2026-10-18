from flask import Blueprint, current_app, jsonify, request

from backend.app.db.repository import ProjectRepository, SimpleRepository
from backend.app.routes.projects import auth_or_error
from backend.app.services.embedding_service import embedding_provider_for_project
from backend.app.services.llm_client import generate_text_with_fallback
from backend.app.services.rag import build_grounded_prompt
from backend.app.services.vector_store import TursoVectorStore

query_bp = Blueprint("query", __name__)


@query_bp.post("/<project_id>/query")
def query_project(project_id: str):
    auth, error = auth_or_error()
    if error:
        return error
    project = ProjectRepository(
        current_app.config["TURSO_DATABASE_URL"], current_app.config["TURSO_AUTH_TOKEN"]
    ).get(project_id, auth.organization_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404
    payload = request.get_json(silent=True) or {}
    message = str(payload.get("message", "")).strip()
    if not message:
        return jsonify({"error": "message is required"}), 400
    mode = payload.get("mode") or project["default_query_mode"]
    runs = SimpleRepository(
        current_app.config["TURSO_DATABASE_URL"], current_app.config["TURSO_AUTH_TOKEN"], "query_runs", "qry"
    )
    store = TursoVectorStore(current_app.config["TURSO_DATABASE_URL"], current_app.config["TURSO_AUTH_TOKEN"])
    if not store.has_embeddings(project_id):
        run = runs.create(
            {
                "project_id": project_id,
                "organization_id": auth.organization_id,
                "conversation_id": payload.get("conversation_id"),
                "user_id": auth.user_id,
                "query": message,
                "answer": "This corpus has no vector embeddings yet.",
                "retrieval_mode": mode,
                "status": "completed",
            }
        )
        return jsonify({"answer": run["answer"], "project_id": project_id, "query_run_id": run["id"], "mode": mode, "sources": []})
    try:
        query_vector = embedding_provider_for_project(current_app.config, project).embed_query(message)
        chunks = store.search(project_id, query_vector)
        answer = generate_text_with_fallback(
            current_app.config,
            [{"role": "user", "content": build_grounded_prompt(message, chunks)}],
        )
    except Exception as exc:  # noqa: BLE001
        run = runs.create(
            {
                "project_id": project_id,
                "organization_id": auth.organization_id,
                "conversation_id": payload.get("conversation_id"),
                "user_id": auth.user_id,
                "query": message,
                "answer": str(exc),
                "retrieval_mode": mode,
                "status": "failed",
            }
        )
        return jsonify({"error": "Vector retrieval failed", "query_run_id": run["id"]}), 503
    run = runs.create(
        {
            "project_id": project_id,
            "organization_id": auth.organization_id,
            "conversation_id": payload.get("conversation_id"),
            "user_id": auth.user_id,
            "query": message,
            "answer": answer,
            "retrieval_mode": mode,
            "status": "completed",
        }
    )
    return jsonify(
        {
            "answer": run["answer"],
            "project_id": project_id,
            "query_run_id": run["id"],
            "mode": mode,
            "sources": [
                {"chunk_id": chunk.chunk_id, "document_id": chunk.document_id, "file_name": chunk.file_name, "score": chunk.score}
                for chunk in chunks
            ],
        }
    )
