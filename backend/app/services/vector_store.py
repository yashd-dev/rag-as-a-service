import json

from backend.app.db.connection import db
from backend.app.db.repository import now_ms, rows_to_dicts
from backend.app.services.rag import RetrievedChunk


class TursoVectorStore:
    def __init__(self, database_url: str, auth_token: str):
        self.database_url = database_url
        self.auth_token = auth_token

    def upsert(
        self, project: dict, chunks: list[dict], vectors: list[list[float]]
    ) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("Chunk and embedding counts must match")
        timestamp = now_ms()
        with db(self.database_url, self.auth_token) as conn:
            for chunk, vector in zip(chunks, vectors, strict=True):
                conn.execute(
                    """
                    INSERT INTO chunk_embeddings(
                        id, project_id, organization_id, document_id, content, embedding, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, vector32(?), ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        content = excluded.content,
                        embedding = excluded.embedding,
                        updated_at = excluded.updated_at
                    """,
                    (
                        chunk["id"],
                        project["id"],
                        project["organization_id"],
                        chunk["document_id"],
                        chunk["content"],
                        json.dumps(vector),
                        timestamp,
                        timestamp,
                    ),
                )

    def existing_ids(self, project_id: str, chunk_ids: list[str]) -> set[str]:
        if not chunk_ids:
            return set()
        placeholders = ", ".join("?" for _ in chunk_ids)
        with db(self.database_url, self.auth_token) as conn:
            cursor = conn.execute(
                f"SELECT id FROM chunk_embeddings WHERE project_id = ? AND id IN ({placeholders})",
                (project_id, *chunk_ids),
            )
            return {row[0] for row in cursor.fetchall()}

    def has_embeddings(self, project_id: str) -> bool:
        with db(self.database_url, self.auth_token) as conn:
            row = conn.execute(
                "SELECT 1 FROM chunk_embeddings WHERE project_id = ? LIMIT 1",
                (project_id,),
            ).fetchone()
        return row is not None

    def search(
        self, project_id: str, vector: list[float], limit: int = 8
    ) -> list[RetrievedChunk]:
        with db(self.database_url, self.auth_token) as conn:
            cursor = conn.execute(
                """
                SELECT c.id, c.document_id, c.content,
                       vector_distance_cos(c.embedding, vector32(?)) AS distance,
                       d.file_name
                FROM chunk_embeddings AS c
                LEFT JOIN documents AS d ON d.id = c.document_id
                WHERE c.project_id = ?
                ORDER BY distance
                LIMIT ?
                """,
                (json.dumps(vector), project_id, limit),
            )
            rows = rows_to_dicts(cursor)
        return [
            RetrievedChunk(
                chunk_id=row["id"],
                document_id=row["document_id"],
                content=row["content"],
                score=1 - float(row["distance"]),
                file_name=row["file_name"],
            )
            for row in rows
        ]
