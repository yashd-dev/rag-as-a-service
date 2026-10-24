from flask import Blueprint, current_app, jsonify, request

from backend.app.db.repository import SimpleRepository
from backend.app.routes.projects import corpus_or_error

conversations_bp = Blueprint("conversations", __name__)


@conversations_bp.post("/projects/<project_id>/conversations")
def create_conversation(project_id: str):
    auth, _, error = corpus_or_error(project_id)
    if error:
        return error
    row = SimpleRepository(
        current_app.config["TURSO_DATABASE_URL"],
        current_app.config["TURSO_AUTH_TOKEN"],
        "conversations",
        "conv",
    ).create(
        {
            "project_id": project_id,
            "organization_id": auth.organization_id,
            "user_id": auth.user_id,
            "title": (request.get_json(silent=True) or {}).get("title"),
        }
    )
    return jsonify(row), 201
