from flask import Blueprint, Response, current_app, jsonify

from backend.app.db.repository import ProjectRepository
from backend.app.routes.projects import auth_or_error
from backend.app.services.graph_store import Neo4jGraphStore, render_graph_html

graph_bp = Blueprint("graph", __name__)


def graph_store() -> Neo4jGraphStore:
    return Neo4jGraphStore(
        current_app.config["NEO4J_URI"],
        current_app.config["NEO4J_USERNAME"],
        current_app.config["NEO4J_PASSWORD"],
    )


def project_or_error(project_id: str, organization_id: str):
    project = ProjectRepository(
        current_app.config["TURSO_DATABASE_URL"], current_app.config["TURSO_AUTH_TOKEN"]
    ).get(project_id, organization_id)
    if not project:
        return None, (jsonify({"error": "Project not found"}), 404)
    return project, None


@graph_bp.get("/<project_id>/graph/status")
def graph_status(project_id: str):
    auth, error = auth_or_error()
    if error:
        return error
    _project, error = project_or_error(project_id, auth.organization_id)
    if error:
        return error
    store = graph_store()
    try:
        return jsonify(store.project_status(project_id, auth.organization_id))
    finally:
        store.close()


@graph_bp.get("/<project_id>/graph")
def graph_html(project_id: str):
    auth, error = auth_or_error()
    if error:
        return error
    _project, error = project_or_error(project_id, auth.organization_id)
    if error:
        return error
    store = graph_store()
    try:
        html = render_graph_html(store.project_graph(project_id, auth.organization_id))
    finally:
        store.close()
    return Response(html, mimetype="text/html")


@graph_bp.get("/<project_id>/graph/data")
def graph_data(project_id: str):
    auth, error = auth_or_error()
    if error:
        return error
    _project, error = project_or_error(project_id, auth.organization_id)
    if error:
        return error
    store = graph_store()
    try:
        return jsonify(store.project_graph(project_id, auth.organization_id))
    finally:
        store.close()
