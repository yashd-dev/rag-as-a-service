"""Workspace ownership is independent of a shared corpus's retrieval scope."""

from dataclasses import dataclass

from backend.app.db.connection import db
from backend.app.db.repository import ProjectRepository, row_to_dict


class CorpusAccessError(RuntimeError):
    def __init__(self, code, status):
        super().__init__(code)
        self.code, self.status = code, status


@dataclass(frozen=True)
class CorpusScope:
    project: dict
    retrieval_project: dict
    read_only: bool

    def readiness(self, status):
        return status | {
            "project_id": self.project["id"],
            "organization_id": self.project["organization_id"],
            "read_only": self.read_only,
            "documents": [
                item | {"retry_eligible": False} if self.read_only else item
                for item in status["documents"]
            ],
        }


class CorpusAccess:
    def __init__(self, config):
        self.url = config["TURSO_DATABASE_URL"]
        self.token = config["TURSO_AUTH_TOKEN"]
        self.projects = ProjectRepository(self.url, self.token)

    def legal_project(self):
        with db(self.url, self.token) as conn:
            return row_to_dict(
                conn.execute(
                    "SELECT p.* FROM shared_corpora s JOIN projects p ON p.id = s.project_id WHERE s.id = 'legal'"
                )
            )

    def resolve(self, auth, project_id, *, write=False):
        project = self.projects.get(project_id, auth.organization_id)
        if project is None:
            raise CorpusAccessError("project_not_found", 404)
        with db(self.url, self.token) as conn:
            reference = conn.execute(
                "SELECT shared_corpus_id FROM project_corpus_references WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            registered = conn.execute(
                "SELECT 1 FROM shared_corpora WHERE project_id = ?", (project_id,)
            ).fetchone()
        read_only = bool(reference or registered)
        if write and read_only:
            raise CorpusAccessError("shared_corpus_read_only", 403)
        effective = self.legal_project() if reference else project
        if effective is None:
            raise CorpusAccessError("shared_corpus_unavailable", 503)
        return CorpusScope(project, effective, read_only)

    def describe(self, auth, project):
        scope = self.resolve(auth, project["id"])
        return project | {
            "corpus_source": "legal" if scope.read_only else "private",
            "read_only": scope.read_only,
            "is_shared_reference": scope.project["id"] != scope.retrieval_project["id"],
        }
