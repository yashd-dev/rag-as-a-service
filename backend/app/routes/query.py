from flask import Blueprint, current_app, jsonify, request

from backend.app.db.repository import ProjectRepository, SimpleRepository
from backend.app.routes.projects import auth_or_error

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
    run = SimpleRepository(
        current_app.config["TURSO_DATABASE_URL"], current_app.config["TURSO_AUTH_TOKEN"], "query_runs", "qry"
    ).create(
        {
            "project_id": project_id,
            "organization_id": auth.organization_id,
            "conversation_id": payload.get("conversation_id"),
            "user_id": auth.user_id,
            "query": message,
            "answer": "RAG pipeline is not indexed yet.",
            "retrieval_mode": mode,
            "status": "completed",
        }
    )
    return jsonify({"answer": run["answer"], "project_id": project_id, "query_run_id": run["id"], "mode": mode, "sources": []})
