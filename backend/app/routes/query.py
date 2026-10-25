from flask import Blueprint, current_app, jsonify, request

from backend.app.routes.projects import corpus_or_error
from backend.app.services.passages import resolve_passage
from backend.app.services.query_service import QueryFailure, QueryService
from backend.app.services.retrieval import MODES, RetrievalService, RetrievalUnavailable

query_bp = Blueprint("query", __name__)


@query_bp.after_request
def private_responses(response):
    response.headers["Cache-Control"] = "no-store"
    return response


def authorized_project(project_id):
    if not current_app.config.get("BACKEND_INTERNAL_SECRET"):
        return (
            None,
            None,
            (
                jsonify(
                    {
                        "error": "Trusted backend authentication is not configured",
                        "code": "internal_auth_not_configured",
                    }
                ),
                503,
            ),
        )
    return corpus_or_error(project_id)


@query_bp.post("/<project_id>/query")
def query_project(project_id):
    auth, scope, error = authorized_project(project_id)
    if error:
        return error
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "message is required"}), 400
    mode = (
        scope.project["default_query_mode"]
        if payload.get("mode") is None
        else payload["mode"]
    )
    if not isinstance(mode, str) or mode not in MODES:
        return (
            jsonify(
                {"error": "Unsupported retrieval mode", "code": "unsupported_mode"}
            ),
            400,
        )
    try:
        return jsonify(
            QueryService(
                current_app.config,
                scope.project,
                auth,
                retrieval_project=scope.retrieval_project,
            ).answer(payload.get("message"), mode, payload.get("conversation_id"), payload.get("generation_config"))
        )
    except (QueryFailure, RetrievalUnavailable) as exc:
        result = {
            "error": exc.code.replace("_", " "),
            "code": exc.code,
            "status": "unavailable" if exc.status == 409 else "failed",
            "mode": mode,
        }
        if getattr(exc, "run_id", None):
            result["query_run_id"] = exc.run_id
        if exc.status == 409:
            try:
                result["readiness"] = scope.readiness(
                    RetrievalService(
                        current_app.config, scope.retrieval_project
                    ).status()
                )
            except Exception:  # noqa: BLE001
                # Retain the original safe error if status is also unavailable.
                result["readiness"] = None
        return jsonify(result), exc.status
    except Exception:  # noqa: BLE001
        # Redact database/transport failures at the HTTP boundary.
        return jsonify({"error": "Query unavailable", "code": "query_unavailable"}), 503


@query_bp.get("/<project_id>/passages/<chunk_id>")
def source_passage(project_id, chunk_id):
    _, scope, error = authorized_project(project_id)
    if error:
        return error
    try:
        passage = resolve_passage(
            current_app.config,
            scope.retrieval_project,
            chunk_id,
            citation_project=scope.project,
        )
    except ValueError:
        return (
            jsonify(
                {
                    "error": "Source integrity verification failed",
                    "code": "source_integrity_failed",
                }
            ),
            503,
        )
    except Exception:  # noqa: BLE001
        # Never emit source/store exceptions containing text or credentials.
        return (
            jsonify(
                {"error": "Source passage unavailable", "code": "source_unavailable"}
            ),
            503,
        )
    if passage is None:
        return (
            jsonify({"error": "Source passage not found", "code": "source_not_found"}),
            404,
        )
    return jsonify(passage)
