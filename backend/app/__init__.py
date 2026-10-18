from flask import Flask
from flask_cors import CORS


def create_app(config=None) -> Flask:
    from backend.app.config import Config
    from backend.app.routes.conversations import conversations_bp
    from backend.app.routes.credentials import credentials_bp
    from backend.app.routes.data_sources import data_sources_bp
    from backend.app.routes.documents import documents_bp
    from backend.app.routes.graph import graph_bp
    from backend.app.routes.health import health_bp
    from backend.app.routes.projects import projects_bp
    from backend.app.routes.query import query_bp

    app = Flask(__name__)
    app.config.from_object(config or Config)
    CORS(app)

    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(projects_bp, url_prefix="/api/projects")
    app.register_blueprint(credentials_bp, url_prefix="/api/credentials")
    app.register_blueprint(data_sources_bp, url_prefix="/api/data-sources")
    app.register_blueprint(documents_bp, url_prefix="/api/projects")
    app.register_blueprint(conversations_bp, url_prefix="/api")
    app.register_blueprint(query_bp, url_prefix="/api/projects")
    app.register_blueprint(graph_bp, url_prefix="/api/projects")
    return app
