import re

from backend.app.db.repository import ProjectCreate, ProjectRepository
from backend.app.services.auth_context import AuthContext


class ValidationError(Exception):
    pass


EMBEDDING_MODEL = "google/embeddinggemma-300m"


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

        data = ProjectCreate(
            organization_id=auth.organization_id,
            owner_user_id=auth.user_id,
            name=name,
            slug=slugify(str(payload.get("slug") or name)),
            description=payload.get("description"),
            default_query_mode=payload.get("default_query_mode") or "hybrid",
            # The UI may display alternatives, but Turso vectors always use one
            # model so a project never mixes incompatible vector dimensions.
            embedding_provider="huggingface",
            embedding_model=EMBEDDING_MODEL,
            default_llm_credential_id=payload.get("default_llm_credential_id") or None,
            default_embedding_credential_id=payload.get(
                "default_embedding_credential_id"
            )
            or None,
        )
        return self.repository.create(data)

    def list_projects(self, auth: AuthContext) -> list[dict]:
        return self.repository.list_for_org(auth.organization_id)

    def get_project(self, auth: AuthContext, project_id: str) -> dict | None:
        return self.repository.get(project_id, auth.organization_id)

    def delete_project(self, auth: AuthContext, project_id: str) -> bool:
        return self.repository.delete(project_id, auth.organization_id)
