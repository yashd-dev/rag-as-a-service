from flask import Blueprint, current_app, jsonify, request

from backend.app.db.repository import ProjectRepository
from backend.app.services.auth_context import AuthError, current_auth_context
from backend.app.services.corpus_access import CorpusAccess, CorpusAccessError
from backend.app.services.jobs import Jobs
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


def corpus_or_error(project_id, *, write=False):
    auth, error = auth_or_error()
    if error:
        return None, None, error
    try:
        scope = CorpusAccess(current_app.config).resolve(auth, project_id, write=write)
        return auth, scope, None
    except CorpusAccessError as exc:
        response = jsonify({"error": exc.code.replace("_", " "), "code": exc.code})
        return auth, None, (response, exc.status)
    except Exception:  # noqa: BLE001 - redact application-store failures
        response = jsonify(
            {"error": "Project lookup unavailable", "code": "project_lookup_unavailable"}
        )
        return auth, None, (response, 503)


@projects_bp.post("")
def create_project():
    auth, error = auth_or_error()
    if error:
        return error
    try:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            raise ValidationError("JSON object is required")
        source = payload.get("corpus_source", "private")
        if source not in ("private", "legal"):
            raise ValidationError("Unsupported corpus source")
        access = CorpusAccess(current_app.config)
        if source == "legal" and access.legal_project() is None:
            return jsonify(
                {
                    "error": "Shared legal corpus is not registered",
                    "code": "shared_corpus_unavailable",
                }
            ), 503
        # The target is platform-selected, never a caller-supplied tenant/project.
        project = service().create_project(
            auth, payload, shared_corpus_id="legal" if source == "legal" else None
        )
        project = access.describe(auth, project)
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
    access = CorpusAccess(current_app.config)
    projects = [
        access.describe(auth, project) for project in service().list_projects(auth)
    ]
    return jsonify({"items": projects})


@projects_bp.get("/<project_id>")
def get_project(project_id: str):
    auth, scope, error = corpus_or_error(project_id)
    if error:
        return error
    return jsonify(CorpusAccess(current_app.config).describe(auth, scope.project))


@projects_bp.delete("/<project_id>")
def delete_project(project_id: str):
    auth, scope, error = corpus_or_error(project_id)
    if error:
        return error
    # Deleting a local reference only detaches it; the canonical source is protected.
    if scope.read_only and scope.project["id"] == scope.retrieval_project["id"]:
        return jsonify(
            {"error": "Shared corpus is read only", "code": "shared_corpus_read_only"}
        ), 403
    if not scope.read_only:
        try:
            Jobs(current_app.config).remove(scope.project)
        except Exception:  # noqa: BLE001 - preserve metadata on storage failure
            return jsonify({"error": "Deletion unavailable; retry when storage is reachable"}), 503
        return jsonify({"status": "deleted", "file_cleanup": "queued"}), 202
    deleted = service().delete_project(auth, project_id)
    if not deleted:
        return jsonify({"error": "Project not found"}), 404
    return "", 204
