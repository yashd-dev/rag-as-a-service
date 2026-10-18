from flask import Blueprint, current_app, jsonify, request

from backend.app.db.indexing import IndexRepository
from backend.app.db.repository import ProjectRepository
from backend.app.routes.projects import auth_or_error

query_bp = Blueprint("query", __name__)


@query_bp.post("/<project_id>/query")
def query_project(project_id):
    auth, error = auth_or_error()
    if error:
        return error
    project = ProjectRepository(current_app.config["TURSO_DATABASE_URL"], current_app.config["TURSO_AUTH_TOKEN"]).get(project_id, auth.organization_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("message"), str) or not payload["message"].strip():
        return jsonify({"error": "message is required"}), 400
    mode = project["default_query_mode"] if payload.get("mode") is None else payload["mode"]
    if not isinstance(mode, str) or mode not in {"vector", "graph", "hybrid"}:
        return jsonify({"error": "Unsupported retrieval mode"}), 400
    try:
        readiness = IndexRepository(current_app.config).corpus_readiness(project)
    except Exception:  # noqa: BLE001 - redact database/transport failures at HTTP boundary
        return jsonify({"error": "Index readiness unavailable"}), 503
    return jsonify({"error": "Requested retrieval mode is not ready", "mode": mode, "readiness": readiness}), 409
