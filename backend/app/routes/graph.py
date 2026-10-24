from flask import Blueprint, Response, current_app, jsonify

from backend.app.routes.projects import corpus_or_error
from backend.app.services.graph_store import Neo4jGraphStore, render_graph_html

graph_bp = Blueprint("graph", __name__)


def graph_store() -> Neo4jGraphStore:
    return Neo4jGraphStore(
        current_app.config["NEO4J_URI"],
        current_app.config["NEO4J_USERNAME"],
        current_app.config["NEO4J_PASSWORD"],
    )


@graph_bp.get("/<project_id>/graph/status")
def graph_status(project_id: str):
    _, scope, error = corpus_or_error(project_id)
    if error:
        return error
    store = graph_store()
    try:
        return jsonify(
            store.project_status(
                scope.retrieval_project["id"],
                scope.retrieval_project["organization_id"],
            )
        )
    finally:
        store.close()


@graph_bp.get("/<project_id>/graph")
def graph_html(project_id: str):
    _, scope, error = corpus_or_error(project_id)
    if error:
        return error
    store = graph_store()
    try:
        html = render_graph_html(
            store.project_graph(
                scope.retrieval_project["id"],
                scope.retrieval_project["organization_id"],
            )
        )
    finally:
        store.close()
    return Response(html, mimetype="text/html")


@graph_bp.get("/<project_id>/graph/data")
def graph_data(project_id: str):
    _, scope, error = corpus_or_error(project_id)
    if error:
        return error
    store = graph_store()
    try:
        return jsonify(
            store.project_graph(
                scope.retrieval_project["id"],
                scope.retrieval_project["organization_id"],
            )
        )
    finally:
        store.close()
