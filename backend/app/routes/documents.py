from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from werkzeug.utils import secure_filename

from backend.app.db.repository import SimpleRepository
from backend.app.routes.projects import corpus_or_error
from backend.app.services.jobs import FORMATS, Jobs
from backend.app.services.retrieval import RetrievalService

documents_bp = Blueprint("documents", __name__)


@documents_bp.post("/<project_id>/documents/upload")
def create_document(project_id: str):
    auth, scope, error = corpus_or_error(project_id, write=True)
    if error:
        return error
    uploaded_files = request.files.getlist("file")
    if not uploaded_files:
        return jsonify({"error": "Multipart file upload is required"}), 400
    filenames = [secure_filename(file.filename or "") for file in uploaded_files]
    if not all(filenames):
        return jsonify({"error": "A valid filename is required"}), 400
    if any(Path(name).suffix.lower() not in FORMATS for name in filenames):
        return jsonify({"error": "Supported formats: PDF with embedded text, TXT, MD, CSV, JSON", "code": "unsupported_format"}), 415
    max_bytes = int(current_app.config["MAX_UPLOAD_MB"]) * 1024 * 1024
    if request.content_length and request.content_length > max_bytes:
        return (
            jsonify(
                {"error": f"file exceeds {current_app.config['MAX_UPLOAD_MB']}MB limit"}
            ),
            413,
        )
    queue, items, errors = Jobs(current_app.config), [], []
    for file, filename in zip(uploaded_files, filenames, strict=True):
        try:
            job = queue.upload(scope.project, auth.user_id, file, filename)
            items.append({"document_id": job["document_id"], "job_id": job["document_id"], "project_id": project_id, "job": job})
        except ValueError as exc:
            code = str(exc) if str(exc) in {"file_too_large", "empty_file"} else "Upload could not be queued"
            errors.append({"file_name": filename, "error": code})
        except Exception:  # noqa: BLE001 - redact intake/store failures
            errors.append({"file_name": filename, "error": "Upload could not be queued"})
    if not items:
        return jsonify({"error": "No uploads accepted", "errors": errors}), 400
    return jsonify({"items": items, "errors": errors}), 202


@documents_bp.get("/<project_id>/jobs")
def list_jobs(project_id):
    _, scope, error = corpus_or_error(project_id)
    if error:
        return error
    return jsonify({"items": [] if scope.read_only else Jobs(current_app.config).list(scope.project)})


@documents_bp.post("/<project_id>/jobs/<document_id>/retry")
def retry_job(project_id, document_id):
    _, scope, error = corpus_or_error(project_id, write=True)
    if error:
        return error
    if not Jobs(current_app.config).retry(scope.project, document_id):
        return jsonify({"error": "Job is not retryable", "code": "job_not_retryable"}), 409
    return jsonify({"state": "queued"}), 202


@documents_bp.get("/<project_id>/documents")
def list_documents(project_id: str):
    _, scope, error = corpus_or_error(project_id)
    if error:
        return error
    project = scope.retrieval_project
    rows = [
        row
        for row in SimpleRepository(
            current_app.config["TURSO_DATABASE_URL"],
            current_app.config["TURSO_AUTH_TOKEN"],
            "documents",
            "doc",
        ).list_for_org(project["organization_id"])
        if row["project_id"] == project["id"]
    ]
    try:
        readiness = {
            item["document_id"]: item
            for item in scope.readiness(
                RetrievalService(current_app.config, project).status()
            )["documents"]
        }
    except Exception:  # noqa: BLE001
        # Read-only status failures must not leak connection details.
        return (
            jsonify(
                {
                    "error": "Index readiness unavailable",
                    "code": "readiness_unavailable",
                }
            ),
            503,
        )
    for row in rows:
        row["readiness"] = readiness[row["id"]]
        row["legacy_status"] = row["status"]
        row["status"] = row["readiness"]["state"]
        if scope.read_only:
            # Expose source content/identity, not the platform uploader's identity.
            row.pop("uploaded_by_user_id", None)
            row["project_id"] = scope.project["id"]
            row["organization_id"] = scope.project["organization_id"]
    return jsonify({"items": rows})


@documents_bp.get("/<project_id>/indexing/status")
def indexing_status(project_id):
    _, scope, error = corpus_or_error(project_id)
    if error:
        return error
    try:
        return jsonify(
            scope.readiness(
                RetrievalService(current_app.config, scope.retrieval_project).status()
            )
        )
    except Exception:  # noqa: BLE001
        # Redact database/transport failures at the HTTP boundary.
        return jsonify({"error": "Index readiness unavailable"}), 503


@documents_bp.delete("/<project_id>/documents/<document_id>")
def delete_document(project_id: str, document_id: str):
    auth, scope, error = corpus_or_error(project_id, write=True)
    if error:
        return error
    repo = SimpleRepository(
        current_app.config["TURSO_DATABASE_URL"],
        current_app.config["TURSO_AUTH_TOKEN"],
        "documents",
        "doc",
    )
    row = repo.get(document_id, auth.organization_id)
    if not row or row["project_id"] != project_id:
        return jsonify({"error": "Document not found"}), 404
    try:
        Jobs(current_app.config).remove(scope.project, document_id)
    except Exception:  # noqa: BLE001 - preserve metadata on storage failure
        return jsonify({"error": "Deletion unavailable; retry when storage is reachable"}), 503
    return jsonify({"status": "deleted", "file_cleanup": "queued"}), 202
