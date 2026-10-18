import sqlite3
from pathlib import Path

import pytest

from backend.app.db.connection import init_db, migrate_db
from backend.app.db.indexing import IdentityConflict, IndexRepository
from backend.scripts.migrate import main


@pytest.fixture
def store(tmp_path):
    path = tmp_path / "app.db"
    config = {"TURSO_DATABASE_URL": "file:" + str(path), "TURSO_AUTH_TOKEN": "local"}
    init_db(config["TURSO_DATABASE_URL"], "local")
    with sqlite3.connect(path) as conn:
        conn.execute("INSERT INTO projects(id,organization_id,owner_user_id,name,slug,created_at,updated_at,embedding_model) VALUES('p','o','u','Project','p',1,1,'legacy-model')")
    return IndexRepository(config), path, {"id": "p", "organization_id": "o", "owner_user_id": "u"}


def query(path, sql, params=()):
    with sqlite3.connect(path) as conn:
        return conn.execute(sql, params).fetchall()


def test_repeatable_migration_preserves_legacy_rows_and_backup(store, tmp_path):
    repo, path, _ = store
    env = tmp_path / ".env"
    env.write_text(f"TURSO_DATABASE_URL={repo.url}\nTURSO_AUTH_TOKEN=local\n")
    before = path.read_bytes()
    main(["--env-file", str(env)])
    assert path.read_bytes() == before
    snapshot = tmp_path / "backup.db"
    main(["--env-file", str(env), "--apply", "--backup", str(snapshot)])
    assert snapshot.stat().st_mode & 0o777 == 0o600
    assert query(snapshot, "SELECT * FROM projects") == query(path, "SELECT * FROM projects")
    with sqlite3.connect(path) as conn:
        conn.execute("DROP TABLE canonical_chunks")
        conn.execute("DROP TABLE index_generations")
        conn.execute("DROP TABLE document_sources")
        conn.execute("INSERT INTO documents VALUES('legacy','p','o','u','old.pdf','ready',1,1)")
        migrate_db(conn)
        migrate_db(conn)
    assert query(path, "SELECT embedding_model FROM projects") == [("legacy-model",)]
    assert query(path, "SELECT id,status FROM documents") == [("legacy", "ready")]
    with pytest.raises(FileExistsError):
        main(["--env-file", str(env), "--apply", "--backup", str(snapshot)])


def test_replay_same_source_keeps_identity_generation_and_exact_spans(store):
    repo, path, project = store
    text = "Article 21.\n\n" * 400
    metadata = {"url": "https://example.test/judgment", "pages": [{"page": 1, "start": 0, "end": len(text)}]}
    before = path.read_bytes()
    plan = repo.stage(project, "source", "record", text, metadata, dry_run=True)
    assert path.read_bytes() == before
    first = repo.stage(project, "source", "record", text, metadata)
    second = repo.stage(project, "source", "record", text, metadata)
    assert plan["generation"] == first["generation"] == second["generation"]
    assert query(path, "SELECT count(*) FROM documents") == [(1,)]
    assert query(path, "SELECT attempts FROM index_generations") == [(1,)]
    for content, start, end, pages in query(path, "SELECT content,start_char,end_char,source_pages FROM canonical_chunks"):
        assert content == text[start:end] and '"page": 1' in pages


def test_legacy_id_adopted_only_once_and_ambiguity_rejected(store):
    repo, path, project = store
    with sqlite3.connect(path) as conn:
        conn.execute("INSERT INTO documents VALUES('old','p','o','u','judgment','ready',1,1)")
    result = repo.stage(project, "source", 12, "Source text", file_name="judgment")
    assert result["document_id"] == "old"
    with pytest.raises(IdentityConflict):
        repo.stage(project, "other-source", 12, "Other text", file_name="judgment")
    with sqlite3.connect(path) as conn:
        for value in ("a", "b"):
            conn.execute("INSERT INTO documents VALUES(?,'p','o','u','ambiguous','pending',1,1)", (value,))
    with pytest.raises(IdentityConflict):
        repo.stage(project, "source", "ambiguous", "Text", file_name="ambiguous")


def test_generations_preserved_and_recipe_change_invalidates(store):
    repo, path, project = store
    first = repo.stage(project, "s", 1, "First version")
    second = repo.stage(project, "s", 1, "Changed source")
    repo.recipe = repo.recipe | {"embedding_model": "changed-model"}
    third = repo.stage(project, "s", 1, "Changed source")
    assert len({first["generation"], second["generation"], third["generation"]}) == 3
    assert query(path, "SELECT count(*) FROM documents") == [(1,)]
    assert query(path, "SELECT count(*) FROM index_generations") == [(3,)]


def test_failure_and_expired_processing_retry_durably(store, monkeypatch):
    repo, path, project = store
    from backend.app.db import indexing
    original = indexing.TextChunker.chunk
    monkeypatch.setattr(indexing.TextChunker, "chunk", lambda *args: (_ for _ in ()).throw(RuntimeError("private payload")))
    with pytest.raises(RuntimeError):
        repo.stage(project, "s", 1, "OCR input")
    assert query(path, "SELECT state,error_code,attempts FROM index_generations") == [("failed", "RuntimeError", 1)]
    monkeypatch.setattr(indexing.TextChunker, "chunk", original)
    repo.stage(project, "s", 1, "OCR input")
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE index_generations SET state='processing', lease_until=0")
    repo.stage(project, "s", 1, "OCR input")
    assert query(path, "SELECT state,attempts FROM index_generations") == [("text_ready", 3)]
    assert query(path, "SELECT count(*) FROM canonical_chunks") == [(1,)]


def test_scope_and_live_lease_reject_competing_work(store):
    repo, path, project = store
    result = repo.stage(project, "s", 1, "OCR")
    with pytest.raises(IdentityConflict):
        repo.stage(project | {"organization_id": "foreign"}, "s", 1, "OCR", document_id=result["document_id"])
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE index_generations SET state='processing',lease_until=9999999999999")
    assert repo.stage(project, "s", 1, "Changed text")["busy"] is True
    assert query(path, "SELECT count(*) FROM index_generations") == [(1,)]


def test_migration_failure_rolls_back(store, monkeypatch):
    from backend.app.db import connection
    repo, path, _ = store
    with pytest.raises(RuntimeError), connection.db(repo.url, repo.token) as conn:
        conn.execute("UPDATE projects SET embedding_model='wrong'")
        raise RuntimeError("interrupted")
    assert query(path, "SELECT embedding_model FROM projects") == [("legacy-model",)]
    assert Path(path).exists()
