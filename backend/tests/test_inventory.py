import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys

import pytest

from backend.inventory.report import application_report, source_report, vector_status
from backend.inventory.sql import Reader, identifier, open_reader
from backend.scripts.inventory import build_report, main, source_inventory


def database(tmp_path):
    path = tmp_path / "corpus.db"
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE projects (id TEXT, organization_id TEXT,
                embedding_provider TEXT, embedding_model TEXT);
            CREATE TABLE documents (id TEXT, project_id TEXT, organization_id TEXT);
            CREATE TABLE chunk_embeddings (id TEXT, project_id TEXT,
                organization_id TEXT, document_id TEXT, content TEXT, embedding TEXT);
            INSERT INTO projects VALUES ('p', 'o', 'legacy-label', 'not-provenance');
            INSERT INTO documents VALUES ('d', 'p', 'o');
            INSERT INTO chunk_embeddings VALUES
                ('a', 'p', 'o', 'd', 'actual text', '[1, 2, 3]'),
                ('b', 'p', 'o', 'd', 'actual text', '[0, 0, 0]'),
                ('c', 'p', 'o', 'd', 'actual text', NULL),
                ('d', 'p', 'o', 'missing', 'actual text', '[1, 2]'),
                ('e', 'p', 'o', 'd', '', '[1, 2]'),
                ('foreign', 'foreign', 'foreign', 'd', 'private text', '[1, 2]');
        """)
    return path


def args(**kwargs):
    return argparse.Namespace(organization_id="o", project_id="p", source_id=None,
                              discover_scopes=False, probe_model=False, **kwargs)


def test_full_scan_is_scoped_and_never_confuses_labels_with_provenance(tmp_path):
    path = database(tmp_path)
    before = hashlib.sha256(path.read_bytes()).digest()
    with open_reader("file:" + str(path)) as reader:
        # Fixture uses JSON solely to stand in for the native vector_extract API.
        reader.connection.create_function("vector_extract", 1, lambda value: value)
        report = application_report(reader, "o", "p")
        assert report["tables"]["chunk_embeddings"]["count"] == 5
        assert report["vectors"]["dimensions"] == {"3": 2, "2": 2}
        assert report["vectors"]["classification"] == {
            "safe_to_copy": 0, "requires_reembedding": 2,
            "requires_text_provenance_repair": 2, "unknown_blocked": 1,
        }
        assert report["vectors"]["counts"]["resolved_document"] == 4
        assert report["vectors"]["stale_count"] is None
        assert "actual text" not in json.dumps(report)
        with pytest.raises(sqlite3.OperationalError):
            reader.connection.execute("DELETE FROM projects")
    assert hashlib.sha256(path.read_bytes()).digest() == before


def test_missing_schema_is_not_empty_corpus(tmp_path):
    path = tmp_path / "empty.db"
    sqlite3.connect(path).close()
    with open_reader("file:" + str(path)) as reader:
        report = application_report(reader, "o", "p")
    assert report["tables"]["documents"] == {"state": "missing_schema"}
    assert report["blockers"]


def test_native_decoder_failure_is_not_success_or_guessed_blob(tmp_path):
    path = database(tmp_path)
    with open_reader("file:" + str(path)) as reader:
        report = application_report(reader, "o", "p")
    assert report["vectors"]["state"] == "blocked"
    assert "dimensions" not in report["vectors"]


@pytest.mark.parametrize("statement", [
    "DELETE FROM projects", "CREATE TABLE x (id)", "WITH x AS (SELECT 1) DELETE FROM projects",
    "PRAGMA query_only = OFF", "SELECT 1; DELETE FROM projects", "SELECT load_extension('x')",
    "SELECT writefile('path', 'content')",
])
def test_reader_rejects_write_paths_before_driver(statement):
    class NeverExecute:
        def execute(self, *args):
            pytest.fail("Rejected statement reached database")
    with pytest.raises(ValueError):
        Reader(NeverExecute()).query(statement)


def test_no_accidental_file_creation(tmp_path):
    path = tmp_path / "missing.db"
    with pytest.raises(FileNotFoundError), open_reader("file:" + str(path)):
        pytest.fail("Should not connect")
    assert not path.exists()


@pytest.mark.parametrize(("value", "state", "dimension"), [
    (None, "missing", None), ([], "invalid", None), ([True, 2], "invalid", 2),
    ([float("nan")], "invalid", 1), ([float("inf")], "invalid", 1),
    ([0, 0], "invalid", 2), ("not JSON", "invalid", None), ([1, -1], "valid_numeric", 2),
])
def test_vector_validation(value, state, dimension):
    assert vector_status(value) == (state, dimension)


def test_source_mapping_is_discovered_quoted_and_never_emits_text(tmp_path):
    path = tmp_path / "ocr.db"
    with sqlite3.connect(path) as connection:
        connection.executescript('''
            CREATE TABLE "legal source" ("record id" TEXT, "OCR" TEXT, "state" TEXT);
            INSERT INTO "legal source" VALUES ('one', 'private judgment', 'done'),
                ('two', '', 'done'), ('three', NULL, 'pending');
        ''')
    with open_reader("file:" + str(path)) as reader:
        report = source_report(reader, {"table_name": "legal source", "id_column": "record id",
                                       "text_column": "OCR", "status_column": "state", "status_value": "done"})
        assert report["counts"]["total"] == 3
        assert report["eligible_ocr_counts"] == {"rows": 2, "nonempty_text": 1}
        assert "private judgment" not in json.dumps(report)
        assert source_report(reader, {"table_name": "assumed"})["state"] == "mapping_not_verified"
    assert identifier('odd"column') == '"odd""column"'


def test_source_membership_checked_before_decryption(tmp_path):
    path = tmp_path / "sources.db"
    with sqlite3.connect(path) as connection:
        connection.executescript('''
            CREATE TABLE data_sources (id TEXT, organization_id TEXT, source_type TEXT,
                prefix TEXT, endpoint_url TEXT, encrypted_secret_access_key TEXT);
            INSERT INTO data_sources VALUES ('s', 'o', 'turso_ocr',
                '{"project_id":"foreign"}', 'must-not-connect', 'must-not-decrypt');
        ''')
    with open_reader("file:" + str(path)) as reader:
        assert source_inventory(reader, reader.schema(), "o", "p", "s", {}) == {
            "state": "source_project_mismatch"}


def test_standalone_command_imports_no_startup_or_sibling_modules():
    script = '''
import importlib.abc, sys
class BlockStartup(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname == "backend.app" or fullname == "ai" or fullname.startswith(("backend.app.", "ai.", "lightrag")):
            raise AssertionError("Diagnostic attempted forbidden import: " + fullname)
sys.meta_path.insert(0, BlockStartup())
from backend.scripts.inventory import main
try:
    main(["--help"])
except SystemExit as exc:
    assert exc.code == 0
'''
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


def test_report_redacts_driver_exceptions_and_missing_config():
    report = build_report(args(), {"TURSO_DATABASE_URL": "https://private-token@host"})
    assert report["application"]["state"] == "blocked"
    assert "private-token" not in json.dumps(report)
    assert report["gate"] == "CLOSED"
    assert report["neo4j"]["state"] == "blocked"


def test_command_does_not_overwrite_prior_evidence(tmp_path, monkeypatch):
    path = tmp_path / "report.json"
    path.write_text("existing evidence")
    with pytest.raises(FileExistsError):
        main(["--discover-scopes", "--output", str(path)])
    assert path.read_text() == "existing evidence"


def test_neo4j_only_uses_read_transactions(monkeypatch):
    import neo4j

    from backend.inventory.graph import graph_report

    queries = []

    class Transaction:
        def run(self, query, **parameters):
            assert parameters == {"org": "o", "project": "p"}
            assert query.startswith(("MATCH ", "SHOW ", "CALL dbms.components()"))
            queries.append(query)
            return []

    class Session:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute_read(self, callback):
            return callback(Transaction())

    class Driver(Session):
        def session(self, **kwargs):
            assert kwargs["default_access_mode"] == neo4j.READ_ACCESS
            return Session()

    monkeypatch.setattr(neo4j.GraphDatabase, "driver", lambda *a, **kw: Driver())
    report = graph_report("bolt://test", "user", "secret", "o", "p")
    assert len(queries) == 8
    assert len(report["measurements"]) == 8
    assert "secret" not in json.dumps(report)


def test_command_full_run_and_startup_boundary(tmp_path):
    path = database(tmp_path)
    report_path = tmp_path / "report.json"
    # Invoke with an empty environment to prevent configured production access.
    env = {"PATH": os.environ.get("PATH", ""), "TURSO_DATABASE_URL": "file:" + str(path)}
    result = subprocess.run([
        sys.executable, "-m", "backend.scripts.inventory", "--organization-id", "o",
        "--project-id", "p", "--output", str(report_path),
    ], env=env, capture_output=True, text=True, check=False)
    assert result.returncode == 2, result.stderr
    report = json.loads(report_path.read_text())
    assert report["application"]["tables"]["documents"]["count"] == 1
    assert report["application"]["vectors"]["state"] == "blocked"
    assert report["gate"] == "CLOSED"


def test_all_pages_are_measured_not_only_first_sample(tmp_path):
    path = database(tmp_path)
    with sqlite3.connect(path) as connection:
        connection.executemany(
            "INSERT INTO chunk_embeddings VALUES (?, 'p', 'o', 'd', 'text', '[1, 2]')",
            [(f"page-{i:04}",) for i in range(501)],
        )
    with open_reader("file:" + str(path)) as reader:
        reader.connection.create_function("vector_extract", 1, lambda value: value)
        report = application_report(reader, "o", "p")
    assert report["tables"]["chunk_embeddings"]["count"] == 506
    assert report["vectors"]["classification"]["unknown_blocked"] == 502


@pytest.mark.parametrize("readonly", [True, False, None])
def test_remote_sql_described_before_execute_and_refuses_nonreads(monkeypatch, readonly):
    import httpx

    requests = []

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        kind = body["requests"][0]["type"]
        if kind == "describe":
            return httpx.Response(200, json={"baton": "private-baton", "results": [{
                "type": "ok", "response": {"result": {"is_readonly": readonly}}}]})
        if kind == "execute":
            assert readonly is True
            assert body["baton"] == "private-baton"
            assert body["requests"][1] == {"type": "close"}
            return httpx.Response(200, json={"baton": None, "results": [{"type": "ok", "response": {
                "result": {"cols": [{"name": "value"}], "rows": [[{"type": "integer", "value": "1"}]]}}}]})
        assert kind == "close"
        return httpx.Response(200, json={"baton": None, "results": []})

    client_type = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: client_type(
        **kwargs, transport=httpx.MockTransport(respond)))
    with open_reader("libsql://test", "secret-token") as reader:
        if readonly is True:
            assert reader.query("SELECT 1 AS value") == [{"value": 1}]
        else:
            with pytest.raises(RuntimeError):
                reader.query("SELECT 1 AS value")
    assert [r["requests"][0]["type"] for r in requests] == [
        "describe", "execute" if readonly is True else "close"]


def test_model_probe_is_transient_and_reports_measured_width(monkeypatch):
    import httpx

    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(200, json={"embeddings": [[1, 2, 3]]})

    client_type = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: client_type(
        **kwargs, transport=httpx.MockTransport(respond)))
    options = args()
    options.probe_model = True
    report = build_report(options, {"OLLAMA_BASE_URL": "http://model", "OLLAMA_EMBEDDING_MODEL": "configured"})
    assert report["model_probe"]["dimension"] == 3
    assert report["model_probe"]["persisted"] is False
    assert report["model_probe"]["revision"] == "unverified"
    assert len(calls) == 1
    assert calls[0].url.path == "/api/embed"


@pytest.mark.parametrize(("env", "reason"), [
    ({}, "missing_database_url"),
    ({"TURSO_DATABASE_URL": "libsql://private"}, "missing_auth_token"),
    ({"TURSO_DATABASE_URL": "unsupported://private"}, "unsupported_database_url_scheme"),
])
def test_configuration_blockers_are_actionable_without_disclosing_values(env, reason):
    report = build_report(args(), env)
    assert report["application"]["reason"] == reason
    assert "private" not in json.dumps(report)


@pytest.mark.parametrize("payload", [
    {"base_url": "https://foreign-host", "results": []},
    {"baton": "baton", "results": [{"type": "error", "error": {"message": "private"}}]},
])
def test_hrana_description_error_or_foreign_origin_never_executes(monkeypatch, payload):
    import httpx

    requests = []

    def respond(request):
        body = json.loads(request.content)
        requests.extend(r["type"] for r in body["requests"])
        if body["requests"][0]["type"] == "close":
            return httpx.Response(200, json={"results": []})
        return httpx.Response(200, json=payload)

    client_type = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: client_type(
        **kwargs, transport=httpx.MockTransport(respond)))
    with open_reader("libsql://test", "token") as reader, pytest.raises(RuntimeError):
        reader.query("SELECT 1")
    assert "execute" not in requests


def test_cli_dotenv_precedence_matches_backend_without_startup(tmp_path, monkeypatch):
    from backend.scripts import inventory

    env_file = tmp_path / "settings.env"
    env_file.write_text("TURSO_DATABASE_URL=libsql://dotenv\nTURSO_AUTH_TOKEN=dotenv-token\n"
                        "OLLAMA_EMBEDDING_MODEL=dotenv-model\nOLLAMA_BASE_URL\n")
    monkeypatch.setenv("TURSO_DATABASE_URL", "libsql://shell")
    monkeypatch.setenv("TURSO_AUTH_TOKEN", "shell-token")
    monkeypatch.setenv("OLLAMA_EMBEDDING_MODEL", "shell-model")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://shell-model-service")
    captured = {}

    def capture(args, env):
        captured.update(env)
        return {}

    monkeypatch.setattr(inventory, "build_report", capture)
    assert inventory.main(["--env-file", str(env_file), "--discover-scopes",
                           "--output", str(tmp_path / "report.json")]) == 2
    assert captured["TURSO_DATABASE_URL"] == "libsql://dotenv"
    assert captured["TURSO_AUTH_TOKEN"] == "dotenv-token"
    assert captured["OLLAMA_EMBEDDING_MODEL"] == "dotenv-model"
    assert captured["OLLAMA_BASE_URL"] == "http://shell-model-service"
