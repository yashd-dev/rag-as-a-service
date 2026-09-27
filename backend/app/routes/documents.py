from flask import Blueprint, current_app, jsonify, request

from backend.app.db.repository import ProjectRepository, SimpleRepository
from backend.app.routes.projects import auth_or_error

documents_bp = Blueprint("documents", __name__)


@documents_bp.post("/<project_id>/documents/upload")
def create_document(project_id: str):
    auth, error = auth_or_error()
    if error:
        return error
    if not ProjectRepository(current_app.config["TURSO_DATABASE_URL"], current_app.config["TURSO_AUTH_TOKEN"]).get(
        project_id, auth.organization_id
    ):
        return jsonify({"error": "Project not found"}), 404
    payload = request.get_json(silent=True) or {}
    file_name = str(payload.get("file_name", "")).strip()
    if not file_name:
        return jsonify({"error": "file_name is required"}), 400
    repo = SimpleRepository(
        current_app.config["TURSO_DATABASE_URL"], current_app.config["TURSO_AUTH_TOKEN"], "documents", "doc"
    )
    row = repo.create(
        {
            "project_id": project_id,
            "organization_id": auth.organization_id,
            "uploaded_by_user_id": auth.user_id,
            "file_name": file_name,
        }
    )
    return jsonify(row), 201


@documents_bp.get("/<project_id>/documents")
def list_documents(project_id: str):
    auth, error = auth_or_error()
    if error:
        return error
    if not ProjectRepository(current_app.config["TURSO_DATABASE_URL"], current_app.config["TURSO_AUTH_TOKEN"]).get(
        project_id, auth.organization_id
    ):
        return jsonify({"error": "Project not found"}), 404
    rows = [
        row
        for row in SimpleRepository(
            current_app.config["TURSO_DATABASE_URL"], current_app.config["TURSO_AUTH_TOKEN"], "documents", "doc"
        ).list_for_org(auth.organization_id)
        if row["project_id"] == project_id
    ]
    return jsonify({"items": rows})
