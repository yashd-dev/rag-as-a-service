from contextlib import contextmanager
from pathlib import Path

import libsql


def connect(database_url: str, auth_token: str):
    if not database_url:
        raise RuntimeError("TURSO_DATABASE_URL or TURSO_CONNECTION_URL is required")
    if not auth_token:
        raise RuntimeError("TURSO_AUTH_TOKEN is required")
    return libsql.connect(database=database_url, auth_token=auth_token)


def init_db(database_url: str, auth_token: str) -> None:
    schema_path = Path(__file__).with_name("schema.sql")
    with connect(database_url, auth_token) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(schema_path.read_text(encoding="utf-8"))
        migrate_db(conn)


def migrate_db(conn) -> None:
    project_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(projects)").fetchall()
    }
    if "embedding_provider" not in project_columns:
        conn.execute(
            "ALTER TABLE projects ADD COLUMN embedding_provider TEXT NOT NULL DEFAULT 'huggingface'"
        )
    if "embedding_model" not in project_columns:
        conn.execute(
            "ALTER TABLE projects ADD COLUMN embedding_model TEXT NOT NULL DEFAULT 'google/embeddinggemma-300m'"
        )
    # Existing rows may advertise a historical UI choice. All persisted vectors
    # use EmbeddingGemma, so normalize the metadata before creating new vectors.
    conn.execute(
        "UPDATE projects SET embedding_provider = 'huggingface', embedding_model = 'google/embeddinggemma-300m'"
    )
    document_columns = {
        row[1] for row in conn.execute("PRAGMA table_info(documents)").fetchall()
    }
    if "status" not in document_columns:
        conn.execute(
            "ALTER TABLE documents ADD COLUMN status TEXT NOT NULL DEFAULT 'pending'"
        )


@contextmanager
def db(database_url: str, auth_token: str):
    conn = connect(database_url, auth_token)
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
