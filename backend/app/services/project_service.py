import re

from backend.app.db.repository import ProjectCreate, ProjectRepository
from backend.app.services.auth_context import AuthContext


class ValidationError(Exception):
    pass


SUPPORTED_EMBEDDING_MODELS = {
    "huggingface": {
        "nomic-ai/nomic-embed-text-v1",
        "embeddinggemma-300m",
        "google/embeddinggemma-300m",
        "sentence-transformers/all-MiniLM-L6-v2",
    }
}


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "project"


class ProjectService:
    def __init__(self, repository: ProjectRepository):
        self.repository = repository

    def create_project(self, auth: AuthContext, payload: dict) -> dict:
        name = str(payload.get("name", "")).strip()
        if not name:
            raise ValidationError("Project name is required")

        embedding_provider = str(payload.get("embedding_provider") or "huggingface").strip()
        embedding_model = str(
            payload.get("embedding_model") or "sentence-transformers/all-MiniLM-L6-v2"
        ).strip()
        if embedding_model not in SUPPORTED_EMBEDDING_MODELS.get(embedding_provider, set()):
            raise ValidationError("Unsupported embedding model")

        data = ProjectCreate(
            organization_id=auth.organization_id,
            owner_user_id=auth.user_id,
            name=name,
            slug=slugify(str(payload.get("slug") or name)),
            description=payload.get("description"),
            default_query_mode=payload.get("default_query_mode") or "hybrid",
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
        )
        return self.repository.create(data)

    def list_projects(self, auth: AuthContext) -> list[dict]:
        return self.repository.list_for_org(auth.organization_id)

    def get_project(self, auth: AuthContext, project_id: str) -> dict | None:
        return self.repository.get(project_id, auth.organization_id)

    def delete_project(self, auth: AuthContext, project_id: str) -> bool:
        return self.repository.delete(project_id, auth.organization_id)
