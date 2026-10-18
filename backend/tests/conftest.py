import sqlite3

import pytest

from backend.app.db.connection import init_db
from backend.app.db.indexing import IndexRepository


@pytest.fixture
def store(tmp_path):
    path = tmp_path / "app.db"
    config = {"TURSO_DATABASE_URL": "file:" + str(path), "TURSO_AUTH_TOKEN": "local"}
    init_db(config["TURSO_DATABASE_URL"], "local")
    with sqlite3.connect(path) as conn:
        conn.execute("INSERT INTO projects(id,organization_id,owner_user_id,name,slug,created_at,updated_at,embedding_model) VALUES('p','o','u','Project','p',1,1,'legacy-model')")
    return IndexRepository(config), path, {"id": "p", "organization_id": "o", "owner_user_id": "u"}
