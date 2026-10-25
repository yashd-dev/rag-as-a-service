import io
import sqlite3

import pytest
from cryptography.fernet import Fernet

from backend.app.db.connection import migrate_db
from backend.app.db.repository import ProjectCreate, ProjectRepository
from backend.scripts.register_shared_corpus import main as register
from backend.tests import test_query_api
from backend.tests.test_index_state import query

api = test_query_api.api


@pytest.fixture
def shared(api):
    app, client, headers, _, path, _, _, _ = api
    app.config["CREDENTIAL_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
    with sqlite3.connect(path) as conn:
        conn.execute("INSERT INTO shared_corpora VALUES('legal','p')")
    workspaces = []
    for org in ("workspace-a", "workspace-b"):
        identity = headers | {
            "X-Organization-Id": org,
            "X-User-Id": org + "-owner",
            "X-User-Role": "owner",
        }
        response = client.post(
            "/api/projects", headers=identity,
            json={"name": "Legal", "corpus_source": "legal"},
        )
        assert response.status_code == 201
        assert response.json["read_only"] and response.json["corpus_source"] == "legal"
        assert response.json["is_shared_reference"] is True
        workspaces.append((identity, response.json))
    return api, workspaces


def test_two_workspaces_retrieve_same_canonical_evidence_with_private_history(shared):
    (_, client, _, _, path, _, snapshot, _), workspaces = shared
    before = query(path, "SELECT * FROM canonical_chunks")
    for identity, project in workspaces:
        project_id = project["id"]
        conversation = client.post(
            f"/api/projects/{project_id}/conversations",
            headers=identity, json={"title": "Private conversation"},
        )
        assert conversation.status_code == 201
        response = client.post(
            f"/api/projects/{project_id}/query", headers=identity,
            json={
                "message": "vector question", "mode": "vector",
                "conversation_id": conversation.json["id"],
            },
        )
        assert response.status_code == 200 and response.json["status"] == "answered"
        assert response.json["project_id"] == project_id
        source = response.json["sources"][0]
        assert source["chunk_id"] in {row["id"] for row in snapshot["rows"]}
        assert source["source_view_url"].startswith(
            f"/api/projects/{project_id}/passages/"
        )
        passage = client.get(source["source_view_url"], headers=identity)
        assert passage.status_code == 200
        assert passage.json["citation_id"] == source["citation_id"]
        assert passage.json["content"] == source["excerpt"]
        documents = client.get(f"/api/projects/{project_id}/documents", headers=identity)
        assert documents.status_code == 200 and len(documents.json["items"]) == 2
        assert all(
            row["organization_id"] == identity["X-Organization-Id"]
            and "uploaded_by_user_id" not in row
            for row in documents.json["items"]
        )
        status = client.get(
            f"/api/projects/{project_id}/indexing/status", headers=identity
        )
        assert status.status_code == 200 and status.json["capabilities"]["vector"]
        assert status.json["project_id"] == project_id
        assert status.json["organization_id"] == identity["X-Organization-Id"]
        assert not any(item["retry_eligible"] for item in status.json["documents"])
    assert query(path, "SELECT * FROM canonical_chunks") == before
    assert query(path, "SELECT count(*) FROM documents") == [(2,)]
    assert query(
        path,
        "SELECT organization_id,user_id,project_id FROM query_runs ORDER BY organization_id",
    ) == [
        (identity["X-Organization-Id"], identity["X-User-Id"], project["id"])
        for identity, project in workspaces
    ]


def test_workspace_owners_cannot_mutate_shared_source_or_other_references(shared):
    (_, client, owner_headers, _, path, _, snapshot, _), workspaces = shared
    document_id = snapshot["rows"][0]["document_id"]
    before = query(path, "SELECT * FROM documents")
    for identity, project in workspaces + [
        (owner_headers | {"X-User-Role": "owner"}, {"id": "p"})
    ]:
        base = f"/api/projects/{project['id']}"
        for response in (
            client.post(
                base + "/documents/upload", headers=identity,
                json={"file_name": "evil.txt"},
            ),
            client.post(
                base + "/documents/upload", headers=identity,
                data={"file": (io.BytesIO(b"Must not be saved"), "evil.txt")},
            ),
            client.delete(base + "/documents/" + document_id, headers=identity),
            client.post(
                "/api/data-sources", headers=identity,
                json={"source_type": "turso_ocr", "project_id": project["id"]},
            ),
        ):
            assert response.status_code == 403
            assert response.json["code"] == "shared_corpus_read_only"
    assert client.delete("/api/projects/p", headers=owner_headers).status_code == 403
    canonical = client.get("/api/projects/p", headers=owner_headers).json
    assert canonical["read_only"] and canonical["is_shared_reference"] is False
    (a_headers, a), (b_headers, b) = workspaces
    assert client.delete(f"/api/projects/{a['id']}", headers=b_headers).status_code == 404
    assert client.delete(f"/api/projects/{a['id']}", headers=a_headers).status_code == 204
    assert query(path, "SELECT * FROM documents") == before
    assert query(path, "SELECT project_id FROM shared_corpora") == [("p",)]
    assert client.post(
        f"/api/projects/{b['id']}/query", headers=b_headers,
        json={"message": "vector question", "mode": "vector"},
    ).status_code == 200


def test_private_projects_sources_conversations_and_credentials_stay_private(shared, monkeypatch):
    (_, client, _, repository, path, _, snapshot, _), workspaces = shared
    (a_headers, a), (b_headers, b) = workspaces
    private = client.post(
        "/api/projects", headers=a_headers, json={"name": "Private"}
    ).json
    repository.stage(
        private, "upload", "private", "Workspace A confidential text",
        file_name="private.txt",
    )
    private_chunk = query(
        path,
        "SELECT c.id FROM canonical_chunks c JOIN index_generations g ON g.id=c.generation_id WHERE g.project_id=?",
        (private["id"],),
    )[0][0]
    for url in (
        f"/api/projects/{private['id']}",
        f"/api/projects/{private['id']}/documents",
        f"/api/projects/{private['id']}/passages/{private_chunk}",
        f"/api/projects/{a['id']}/passages/{snapshot['rows'][0]['id']}",
        "/api/projects/p",
    ):
        assert client.get(url, headers=b_headers).status_code == 404
        assert client.get(url).status_code == 401
    assert client.get(
        f"/api/projects/{b['id']}/passages/{private_chunk}", headers=b_headers
    ).status_code == 404
    listed = client.get("/api/projects", headers=b_headers)
    assert {row["id"] for row in listed.json["items"]} == {b["id"]}
    monkeypatch.setattr("backend.app.services.credential_service.validate_key_model", lambda *args: "https://api.openai.com/v1")
    credential = client.post(
        "/api/credentials", headers=a_headers,
        json={
            "name": "Private BYOK", "provider": "fixture",
            "credential_type": "llm", "api_key": "private-fixture-key",
        },
    )
    assert credential.status_code == 201
    assert client.get("/api/credentials", headers=b_headers).json["items"] == []
    conversation = client.post(
        f"/api/projects/{a['id']}/conversations", headers=a_headers, json={}
    ).json
    response = client.post(
        f"/api/projects/{b['id']}/query", headers=b_headers,
        json={
            "message": "question", "mode": "vector",
            "conversation_id": conversation["id"],
        },
    )
    assert response.status_code == 404
    assert response.json["code"] == "conversation_not_found"
    assert query(path, "SELECT count(*) FROM query_runs") == [(0,)]


def test_registration_is_explicit_repeatable_and_preserves_data(api, tmp_path):
    _, client, headers, repository, path, _, _, _ = api
    env = tmp_path / "env"
    env.write_text(f"TURSO_DATABASE_URL={repository.url}\nTURSO_AUTH_TOKEN=local\n")
    args = ["--env-file", str(env), "--organization-id", "o", "--project-id", "p"]
    original = path.read_bytes()
    register(args)
    assert path.read_bytes() == original
    response = client.post(
        "/api/projects", headers=headers,
        json={"name": "Legal", "corpus_source": "legal"},
    )
    assert response.status_code == 503
    assert query(path, "SELECT count(*) FROM projects") == [(1,)]
    backup = tmp_path / "backup.db"
    register(args + ["--apply", "--backup", str(backup)])
    assert query(backup, "SELECT * FROM documents") == query(path, "SELECT * FROM documents")
    assert query(backup, "SELECT * FROM canonical_chunks") == query(
        path, "SELECT * FROM canonical_chunks"
    )
    assert backup.stat().st_mode & 0o777 == 0o600
    registered = path.read_bytes()
    register(args + ["--apply", "--backup", str(tmp_path / "unused.db")])
    assert path.read_bytes() == registered
    with sqlite3.connect(path) as conn:
        migrate_db(conn)
        migrate_db(conn)
    assert query(path, "SELECT project_id FROM shared_corpora") == [("p",)]
    other = ProjectRepository(repository.url, repository.token).create(
        ProjectCreate("o", "u", "Other", "other")
    )
    with pytest.raises(ValueError, match="different project"):
        register(args[:-1] + [other["id"]])


def test_database_constraints_reject_retargeting_and_ingestion_into_references(shared):
    (_, _, _, repository, path, _, _, _), workspaces = shared
    project = workspaces[0][1]
    for sql in (
        "UPDATE shared_corpora SET project_id='p'",
        "UPDATE project_corpus_references SET shared_corpus_id='legal'",
        f"INSERT INTO documents VALUES('bad','{project['id']}','workspace-a','u','bad.txt','pending',1,1)",
    ):
        with sqlite3.connect(path) as conn, pytest.raises(sqlite3.IntegrityError):
            conn.execute(sql)
    with pytest.raises(Exception, match="shared corpus reference"):
        repository.stage(project, "upload", "bad", "Should never be ingested")
    assert query(path, "SELECT count(*) FROM documents") == [(2,)]


def test_graph_read_routes_use_the_canonical_scope(shared, monkeypatch):
    (_, client, _, _, _, _, _, _), workspaces = shared
    identity, project = workspaces[0]
    calls = []

    class Graph:
        def project_status(self, project_id, organization_id):
            calls.append((project_id, organization_id))
            return {"nodes": 0}

        def project_graph(self, project_id, organization_id):
            calls.append((project_id, organization_id))
            return {"nodes": [], "edges": []}

        def close(self):
            pass

    monkeypatch.setattr("backend.app.routes.graph.graph_store", Graph)
    monkeypatch.setattr(
        "backend.app.routes.graph.render_graph_html", lambda graph: "<html></html>"
    )
    for suffix in ("/graph/status", "/graph/data", "/graph"):
        response = client.get(f"/api/projects/{project['id']}" + suffix, headers=identity)
        assert response.status_code == 200
    assert calls == [("p", "o")] * 3


def test_unpublished_shared_mode_reports_local_scope_and_no_retry_control(shared):
    (_, client, _, _, _, _, _, state), workspaces = shared
    identity, project = workspaces[0]
    state["graph_ready"] = False
    response = client.post(
        f"/api/projects/{project['id']}/query", headers=identity,
        json={"message": "question", "mode": "graph"},
    )
    assert response.status_code == 409
    assert response.json["readiness"]["project_id"] == project["id"]
    assert not any(
        item["retry_eligible"] for item in response.json["readiness"]["documents"]
    )


def test_missing_internal_secret_denies_project_reads_and_mutations(api):
    app, client, headers, _, path, _, _, _ = api
    app.config["BACKEND_INTERNAL_SECRET"] = ""
    assert client.get("/api/projects", headers=headers).status_code == 401
    assert client.delete("/api/projects/p", headers=headers).status_code == 401
    assert query(path, "SELECT count(*) FROM projects") == [(1,)]
