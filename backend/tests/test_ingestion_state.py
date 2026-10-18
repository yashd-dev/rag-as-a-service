import ast
import io
import json
import os
import re
import sqlite3
from pathlib import Path

import pytest

from backend.app import create_app
from backend.app.services.crypto import SecretBox
from backend.app.services.ingestion_service import (
    IngestionService,
    TursoOcrIngestionService,
)
from backend.tests.test_index_state import query


@pytest.fixture
def source(store, tmp_path):
    repo, path, project = store
    source_path = tmp_path / "ocr.db"
    with sqlite3.connect(source_path) as conn:
        conn.execute("CREATE TABLE pdfs(path TEXT PRIMARY KEY,ocr_text TEXT,ocr_status TEXT,url TEXT)")
        conn.execute("INSERT INTO pdfs VALUES('a','Existing OCR passage','done','https://example.test/a')")
        conn.execute("INSERT INTO pdfs VALUES('b','\n\t\u2003','done','https://example.test/b')")
    config = {"TURSO_DATABASE_URL": repo.url, "TURSO_AUTH_TOKEN": repo.token, "CREDENTIAL_ENCRYPTION_KEY": "test-key"}
    row = {"id": "src", "organization_id": "o", "source_type": "turso_ocr", "endpoint_url": "file:" + str(source_path),
           "encrypted_secret_access_key": SecretBox("test-key").encrypt("local"),
           "prefix": json.dumps({"project_id": "p", "table_name": "pdfs", "id_column": "path", "text_column": "ocr_text", "last_source_id": "z", "batch_size": 1})}
    with sqlite3.connect(path) as conn:
        conn.execute("INSERT INTO data_sources(id,organization_id,owner_user_id,name,source_type,bucket,prefix,endpoint_url,encrypted_secret_access_key,created_at,updated_at) VALUES('src','o','u','OCR','turso_ocr','pdfs',?,?,?,1,1)",
                     (row["prefix"], row["endpoint_url"], row["encrypted_secret_access_key"]))
    return config, row, source_path, project


def test_real_source_dry_run_and_replay_after_failed_advanced_cursor(source, store, monkeypatch):
    config, row, source_path, project = source
    _, path, _ = store
    service = TursoOcrIngestionService(config)
    original_bytes = path.read_bytes(), source_path.read_bytes()
    plan = service.run_background_ingestion(project, row, dry_run=True)
    assert plan["processed_count"] == 1 and plan["excluded_count"] == 1
    assert original_bytes == (path.read_bytes(), source_path.read_bytes())
    from backend.app.db import indexing
    original = indexing.TextChunker.chunk
    monkeypatch.setattr(indexing.TextChunker, "chunk", lambda *args: (_ for _ in ()).throw(RuntimeError("provider secret")))
    failed = service.run_background_ingestion(project, row)
    assert failed["failed_count"] == 1
    assert "provider secret" not in json.dumps(failed)
    monkeypatch.setattr(indexing.TextChunker, "chunk", original)
    persisted = service.sources.get("src", "o")
    assert json.loads(persisted["prefix"])["last_source_id"] == "b"
    success = service.run_background_ingestion(project, persisted)
    replacement = service.run_background_ingestion(project, row | {"id": "replacement-configuration"}, dry_run=True)
    assert replacement["plans"][0]["document_id"] == success["plans"][0]["document_id"]
    assert success["failed_count"] == 0
    assert query(path, "SELECT count(*) FROM documents") == [(1,)]
    assert query(path, "SELECT attempts FROM index_generations") == [(2,)]
    assert source_path.read_bytes() == original_bytes[1]
    metadata = json.loads(query(path, "SELECT source_metadata FROM index_generations")[0][0])
    assert metadata["source_uri"] == "https://example.test/a"
    assert metadata["source_row"]["path"] == "a"


def test_readiness_never_promotes_chunk_only_and_invalidates_corrupt_chunks(store):
    repo, path, project = store
    staged = repo.stage(project, "s", 1, "Source passage")
    readiness = repo.readiness(project, staged["document_id"])
    assert readiness["state"] == "text_ready"
    assert readiness["capabilities"] == {"text": True, "vector": False, "graph": False}
    assert repo.corpus_readiness(project)["counts"]["text_ready"] == 1
    repo.recipe = repo.recipe | {"embedding_model": "new-model"}
    assert repo.readiness(project, staged["document_id"])["state"] == "pending"
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE canonical_chunks SET content='corrupt'")
    repo.recipe = readiness["recipe"]
    assert repo.readiness(project, staged["document_id"])["state"] == "failed"
    assert repo.readiness(project, staged["document_id"])["capabilities"]["text"] is False
    assert repo.corpus_readiness(project)["state"] == "failed"


def test_legacy_ready_and_interrupted_work_are_not_readiness_evidence(store):
    repo, path, project = store
    staged = repo.stage(project, "s", 1, "Passage")
    with sqlite3.connect(path) as conn:
        conn.execute("INSERT INTO documents VALUES('legacy','p','o','u','old.pdf','ready',1,1)")
        conn.execute("UPDATE index_generations SET state='processing',lease_until=0")
    assert repo.readiness(project, "legacy")["state"] == "pending"
    result = repo.readiness(project, staged["document_id"])
    assert result["state"] == "failed" and result["failures"][0]["code"] == "interrupted"
    assert result["capabilities"]["text"] is True
    assert repo.corpus_readiness(project)["counts"]["total"] == 2


def test_partial_graph_failure_preserves_text_without_enabling_retrieval(store):
    repo, path, project = store
    staged = repo.stage(project, "s", 1, "Canonical passage")
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE index_generations SET state='graph_partial',error_code='extraction_failed'")
    ready = repo.readiness(project, staged["document_id"])
    assert ready["state"] == "graph_partial" and ready["retry_eligible"]
    assert ready["capabilities"] == {"text": True, "vector": False, "graph": False}
    assert repo.corpus_readiness(project)["state"] == "graph_partial"


def test_source_cli_defaults_to_read_only_preview(source, store, tmp_path, capsys):
    from backend.scripts.index_source import main
    config, _, source_path, _ = source
    _, path, _ = store
    env = tmp_path / "source.env"
    env.write_text("\n".join(f"{key}={value}" for key, value in config.items()))
    before = path.read_bytes(), source_path.read_bytes()
    assert main(["--env-file", str(env), "--organization-id", "o", "--project-id", "p", "--source-id", "src"]) == 0
    assert json.loads(capsys.readouterr().out)["dry_run"] is True
    assert before == (path.read_bytes(), source_path.read_bytes())


def test_native_pdf_extraction_keeps_page_spans(store, monkeypatch, tmp_path):
    import backend.app.services.ingestion_service as ingestion
    repo, _, project = store
    class Page:
        def __init__(self, text):
            self.text = text

        def extract_text(self):
            return self.text

    monkeypatch.setattr(ingestion, "PdfReader", lambda path: type("PDF", (), {"pages": [Page("Page one."), Page("Page two.")]}))
    service = IngestionService({"TURSO_DATABASE_URL": repo.url, "TURSO_AUTH_TOKEN": repo.token})
    doc = service.register_upload(project, "judgment.pdf", "bytes", "u")
    result = service.ingest_uploaded_file(project, doc, tmp_path / "judgment.pdf")
    assert result["readiness"]["capabilities"]["text"] is True
    text, metadata = service.extract_text(tmp_path / "judgment.pdf")
    assert text[metadata["pages"][1]["start"]:metadata["pages"][1]["end"]] == "Page two."


def test_extraction_failure_persists_retryable_document_failure(store, tmp_path):
    repo, path, project = store
    service = IngestionService({"TURSO_DATABASE_URL": repo.url, "TURSO_AUTH_TOKEN": repo.token})
    doc = service.register_upload(project, "file.unknown", "hash", "u")
    with pytest.raises(Exception, match="Text staging failed"):
        service.ingest_uploaded_file(project, doc, tmp_path / "file.unknown")
    assert repo.readiness(project, doc["id"])["state"] == "failed"
    assert query(path, "SELECT state FROM index_generations") == [("failed",)]


def test_flask_factory_is_write_free_and_exposes_truthful_status(store, tmp_path):
    repo, path, _project = store
    class Config:
        TESTING = True
        TURSO_DATABASE_URL = repo.url
        TURSO_AUTH_TOKEN = repo.token
        BACKEND_INTERNAL_SECRET = "test-secret"
        UPLOAD_DIR = tmp_path / "uploads"
        MAX_UPLOAD_MB = 1
    before = path.read_bytes()
    app = create_app(Config)
    assert path.read_bytes() == before
    from backend.app.routes import documents
    from backend.app.routes import query as query_routes
    from backend.app.services.auth_context import AuthContext
    auth = AuthContext(user_id="u", organization_id="o", role="owner")
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(documents, "auth_or_error", lambda: (auth, None))
        patch.setattr(query_routes, "auth_or_error", lambda: (auth, None))
        client = app.test_client()
        for _ in range(2):
            response = client.post("/api/projects/p/documents/upload", data={"file": (io.BytesIO(b"Source text"), "judgment.txt")})
            assert response.status_code == 201
            assert response.json["status"] == "text_ready"
            assert not response.json["readiness"]["capabilities"]["vector"]
        assert query(path, "SELECT count(*) FROM documents") == [(1,)]
        assert client.get("/api/projects/p/indexing/status").json["state"] == "text_ready"
        for mode in ("vector", "graph", "hybrid"):
            assert client.post("/api/projects/p/query", json={"message": "question", "mode": mode}).status_code == 409
        assert client.post("/api/projects/p/query", json={"message": "question", "mode": []}).status_code == 400
        assert client.post("/api/projects/p/query", json={"message": "question", "mode": ["bad"]}).status_code == 400
        assert client.get("/api/projects/foreign/indexing/status").status_code == 404
        assert client.post("/api/projects/p/documents/upload", json=["invalid"]).status_code == 400


def test_no_sibling_or_lightrag_runtime_dependencies():
    root = Path(__file__).parents[2]
    for path in (root / "backend").rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            assert not any(name.split(".")[0].lower() in {"ai", "lightrag"} for name in names), str(path)
            if isinstance(node, ast.Call):
                function = node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id if isinstance(node.func, ast.Name) else ""
                assert not (function in {"import_module", "__import__"} and any(isinstance(arg, ast.Constant) and str(arg.value).split(".")[0].lower() in {"ai", "lightrag"} for arg in node.args))
    for directory, dirs, files in os.walk(root / "web"):
        dirs[:] = [name for name in dirs if name not in {"node_modules", ".next", ".git"}]
        for name in files:
            if Path(name).suffix in {".ts", ".tsx", ".js", ".mjs"}:
                text = (Path(directory) / name).read_text()
                imports = re.findall(r'''(?:from\s+|import\s*(?:\(\s*)?)["']([^"']+)["']''', text)
                assert all("lightrag" not in module.lower() and "/ai/" not in module for module in imports)
    requirements = (root / "backend/requirements.txt").read_text().lower()
    package = json.loads((root / "web/package.json").read_text())
    assert "lightrag" not in requirements
    assert not any("lightrag" in name.lower() for key in ("dependencies", "devDependencies") for name in package.get(key, {}))
