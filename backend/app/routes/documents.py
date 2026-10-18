import hashlib
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from werkzeug.utils import secure_filename

from backend.app.db.indexing import IndexRepository
from backend.app.db.repository import ProjectRepository, SimpleRepository
from backend.app.routes.projects import auth_or_error
from backend.app.services.ingestion_service import IngestionError, IngestionService

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
    uploaded_files = request.files.getlist("file")
    uploaded_file = uploaded_files[0] if uploaded_files else None
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"error": "JSON object is required"}), 400
    requested_names = [secure_filename(file.filename) for file in uploaded_files if file and file.filename]
    if uploaded_files and any(not file.filename or not secure_filename(file.filename) for file in uploaded_files):
        return jsonify({"error": "A valid filename is required"}), 400
    if not requested_names and payload.get("file_name"):
        requested_names = [str(payload.get("file_name", "")).strip()]
    if not requested_names:
        return jsonify({"error": "file is required"}), 400
    max_bytes = int(current_app.config["MAX_UPLOAD_MB"]) * 1024 * 1024
    if uploaded_file and request.content_length and request.content_length > max_bytes:
        return jsonify({"error": f"file exceeds {current_app.config['MAX_UPLOAD_MB']}MB limit"}), 413
    repo = SimpleRepository(
        current_app.config["TURSO_DATABASE_URL"], current_app.config["TURSO_AUTH_TOKEN"], "documents", "doc"
    )
    project = ProjectRepository(current_app.config["TURSO_DATABASE_URL"], current_app.config["TURSO_AUTH_TOKEN"]).get(
        project_id, auth.organization_id
    )
    rows = []
    errors = []
    ingestion = IngestionService(current_app.config)
    files_to_process = uploaded_files if uploaded_files else [None]
    for index, file in enumerate(files_to_process):
        file_name = secure_filename(file.filename) if file else requested_names[index]
        if file:
            print(
                f"upload start project={project_id} org={auth.organization_id} file={file_name} "
                f"content_length={request.content_length}",
                flush=True,
            )
        row = ingestion.register_upload(project, file_name, hashlib.file_digest(file.stream, "sha256").hexdigest(), auth.user_id) if file else repo.create(
            {
                "project_id": project_id,
                "organization_id": auth.organization_id,
                "uploaded_by_user_id": auth.user_id,
                "file_name": file_name,
                "status": "pending_processing" if file else "pending_upload",
            }
        )
        if file:
            file.stream.seek(0)
            upload_dir = Path(current_app.config["UPLOAD_DIR"]) / auth.organization_id / project_id / row["id"]
            upload_dir.mkdir(parents=True, exist_ok=True)
            file_path = upload_dir / file_name
            file.save(file_path)
            print(f"upload saved document={row['id']} path={file_path} size_bytes={file_path.stat().st_size}", flush=True)
            try:
                row = ingestion.ingest_uploaded_file(project, row, file_path)
                print(f"upload processed document={row['id']} status={row['status']}", flush=True)
            except IngestionError as exc:
                row = repo.get(row["id"], auth.organization_id)
                print(f"upload failed document={row['id']} status={row['status']} error={exc}", flush=True)
                errors.append({"document_id": row["id"], "file_name": file_name, "error": str(exc)})
        row["readiness"] = ingestion.index.readiness(project, row["id"])
        row["status"] = row["readiness"]["state"]
        rows.append(row)
    status_code = 207 if errors else 201
    if len(rows) == 1 and not errors:
        return jsonify(rows[0]), status_code
    return jsonify({"items": rows, "errors": errors}), status_code


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
    index = IndexRepository(current_app.config)
    project = {"id": project_id, "organization_id": auth.organization_id}
    readiness = {item["document_id"]: item for item in index.corpus_readiness(project)["documents"]}
    for row in rows:
        row["readiness"] = readiness[row["id"]]
        row["legacy_status"] = row["status"]
        row["status"] = row["readiness"]["state"]
    return jsonify({"items": rows})


@documents_bp.get("/<project_id>/indexing/status")
def indexing_status(project_id):
    auth, error = auth_or_error()
    if error:
        return error
    project = ProjectRepository(current_app.config["TURSO_DATABASE_URL"], current_app.config["TURSO_AUTH_TOKEN"]).get(project_id, auth.organization_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404
    try:
        return jsonify(IndexRepository(current_app.config).corpus_readiness(project))
    except Exception:  # noqa: BLE001 - redact database/transport failures at HTTP boundary
        return jsonify({"error": "Index readiness unavailable"}), 503


@documents_bp.delete("/<project_id>/documents/<document_id>")
def delete_document(project_id: str, document_id: str):
    auth, error = auth_or_error()
    if error:
        return error
    if not ProjectRepository(current_app.config["TURSO_DATABASE_URL"], current_app.config["TURSO_AUTH_TOKEN"]).get(
        project_id, auth.organization_id
    ):
        return jsonify({"error": "Project not found"}), 404
    repo = SimpleRepository(
        current_app.config["TURSO_DATABASE_URL"], current_app.config["TURSO_AUTH_TOKEN"], "documents", "doc"
    )
    row = repo.get(document_id, auth.organization_id)
    if not row or row["project_id"] != project_id:
        return jsonify({"error": "Document not found"}), 404
    repo.delete(document_id, auth.organization_id)
    return "", 204
