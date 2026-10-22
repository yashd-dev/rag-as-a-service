from flask import Blueprint, current_app, jsonify, request

from backend.app.db.repository import ProjectRepository, SimpleRepository
from backend.app.routes.projects import auth_or_error
from backend.app.services.crypto import SecretBox
from backend.app.services.data_source_service import DataSourceService
from backend.app.services.project_service import ValidationError

data_sources_bp = Blueprint("data_sources", __name__)


def service() -> DataSourceService:
    repo = SimpleRepository(
        current_app.config["TURSO_DATABASE_URL"],
        current_app.config["TURSO_AUTH_TOKEN"],
        "data_sources",
        "src",
    )
    return DataSourceService(
        repo, SecretBox(current_app.config["CREDENTIAL_ENCRYPTION_KEY"])
    )


@data_sources_bp.post("")
def create_data_source():
    auth, error = auth_or_error()
    if error:
        return error
    try:
        payload = request.get_json(silent=True) or {}
        print(
            f"data_source create requested type={payload.get('source_type')} project_id={payload.get('project_id')} "
            f"has_turso_url={bool(str(payload.get('turso_database_url') or '').strip())}",
            flush=True,
        )
        project = None
        if payload.get("source_type") == "turso_ocr" and payload.get("project_id"):
            project = ProjectRepository(
                current_app.config["TURSO_DATABASE_URL"],
                current_app.config["TURSO_AUTH_TOKEN"],
            ).get(str(payload["project_id"]), auth.organization_id)
            if not project:
                return jsonify({"error": "Project not found"}), 404
        row = service().create(auth, payload)
        print(
            f"data_source created id={row['id']} type={row.get('source_type')} project_id={payload.get('project_id')}",
            flush=True,
        )
        return jsonify(row), 201
    except (ValidationError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400


@data_sources_bp.get("")
def list_data_sources():
    auth, error = auth_or_error()
    if error:
        return error
    return jsonify({"items": service().list(auth)})
