from dataclasses import dataclass
import time
import uuid

from backend.app.db.connection import db


def now_ms() -> int:
    return int(time.time() * 1000)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def rows_to_dicts(cursor) -> list[dict]:
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def row_to_dict(cursor) -> dict | None:
    rows = rows_to_dicts(cursor)
    return rows[0] if rows else None


@dataclass(frozen=True)
class ProjectCreate:
    organization_id: str
    owner_user_id: str
    name: str
    slug: str
    description: str | None = None
    default_query_mode: str = "hybrid"
    embedding_provider: str = "huggingface"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"


class ProjectRepository:
    def __init__(self, database_url: str, auth_token: str):
        self.database_url = database_url
        self.auth_token = auth_token

    def create(self, data: ProjectCreate) -> dict:
        project_id = new_id("proj")
        timestamp = now_ms()
        with db(self.database_url, self.auth_token) as conn:
            conn.execute(
                """
                INSERT INTO projects(
                    id, organization_id, owner_user_id, name, slug, description,
                    default_query_mode, embedding_provider, embedding_model,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    data.organization_id,
                    data.owner_user_id,
                    data.name,
                    data.slug,
                    data.description,
                    data.default_query_mode,
                    data.embedding_provider,
                    data.embedding_model,
                    timestamp,
                    timestamp,
                ),
            )
        return self.get(project_id, data.organization_id)

    def list_for_org(self, organization_id: str) -> list[dict]:
        with db(self.database_url, self.auth_token) as conn:
            cursor = conn.execute(
                """
                SELECT * FROM projects
                WHERE organization_id = ?
                ORDER BY created_at DESC
                """,
                (organization_id,),
            )
        return rows_to_dicts(cursor)

    def get(self, project_id: str, organization_id: str) -> dict | None:
        with db(self.database_url, self.auth_token) as conn:
            cursor = conn.execute(
                "SELECT * FROM projects WHERE id = ? AND organization_id = ?",
                (project_id, organization_id),
            )
        return row_to_dict(cursor)

    def delete(self, project_id: str, organization_id: str) -> bool:
        with db(self.database_url, self.auth_token) as conn:
            cursor = conn.execute(
                "DELETE FROM projects WHERE id = ? AND organization_id = ?",
                (project_id, organization_id),
            )
        return cursor.rowcount > 0


class SimpleRepository:
    def __init__(self, database_url: str, auth_token: str, table: str, prefix: str):
        self.database_url = database_url
        self.auth_token = auth_token
        self.table = table
        self.prefix = prefix

    def create(self, values: dict) -> dict:
        row = values | {"id": new_id(self.prefix), "created_at": now_ms(), "updated_at": now_ms()}
        columns = list(row)
        placeholders = ", ".join("?" for _ in columns)
        with db(self.database_url, self.auth_token) as conn:
            conn.execute(
                f"INSERT INTO {self.table} ({', '.join(columns)}) VALUES ({placeholders})",
                tuple(row[column] for column in columns),
            )
        return self.get(row["id"], row["organization_id"])

    def list_for_org(self, organization_id: str) -> list[dict]:
        with db(self.database_url, self.auth_token) as conn:
            cursor = conn.execute(
                f"SELECT * FROM {self.table} WHERE organization_id = ? ORDER BY created_at DESC",
                (organization_id,),
            )
        return rows_to_dicts(cursor)

    def get(self, row_id: str, organization_id: str) -> dict | None:
        with db(self.database_url, self.auth_token) as conn:
            cursor = conn.execute(
                f"SELECT * FROM {self.table} WHERE id = ? AND organization_id = ?",
                (row_id, organization_id),
            )
        return row_to_dict(cursor)
