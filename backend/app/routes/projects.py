from flask import Blueprint, current_app, jsonify, request

from backend.app.db.repository import ProjectRepository
from backend.app.services.auth_context import AuthError, current_auth_context
from backend.app.services.project_service import ProjectService, ValidationError

projects_bp = Blueprint("projects", __name__)


def service() -> ProjectService:
    return ProjectService(
        ProjectRepository(
            current_app.config["TURSO_DATABASE_URL"],
            current_app.config["TURSO_AUTH_TOKEN"],
        )
    )


def auth_or_error():
    try:
        return current_auth_context(), None
    except AuthError as exc:
        return None, (jsonify({"error": str(exc)}), 401)


@projects_bp.post("")
def create_project():
    auth, error = auth_or_error()
    if error:
        return error
    try:
        project = service().create_project(auth, request.get_json(silent=True) or {})
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        if "UNIQUE" not in str(exc).upper():
            raise
        return jsonify({"error": "Project slug already exists"}), 409
    return jsonify(project), 201


@projects_bp.get("")
def list_projects():
    auth, error = auth_or_error()
    if error:
        return error
    return jsonify({"items": service().list_projects(auth)})


@projects_bp.get("/<project_id>")
def get_project(project_id: str):
    auth, error = auth_or_error()
    if error:
        return error
    project = service().get_project(auth, project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404
    return jsonify(project)


@projects_bp.delete("/<project_id>")
def delete_project(project_id: str):
    auth, error = auth_or_error()
    if error:
        return error
    deleted = service().delete_project(auth, project_id)
    if not deleted:
        return jsonify({"error": "Project not found"}), 404
    return "", 204
