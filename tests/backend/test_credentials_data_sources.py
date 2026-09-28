def test_create_credential_never_returns_secret(client, auth_headers):
    response = client.post(
        "/api/credentials",
        headers=auth_headers,
        json={"name": "OpenAI", "provider": "openai", "credential_type": "llm", "api_key": "sk-test1234"},
    )

    assert response.status_code == 201
    body = response.get_json()
    assert "encrypted_api_key" not in body
    assert body["api_key_hint"] == "...1234"

    listed = client.get("/api/credentials", headers=auth_headers).get_json()["items"]
    assert "encrypted_api_key" not in listed[0]


def test_private_data_source_requires_keys(client, auth_headers):
    response = client.post(
        "/api/data-sources",
        headers=auth_headers,
        json={"name": "R2", "source_type": "r2", "bucket": "bucket"},
    )

    assert response.status_code == 400


def test_public_data_source_allows_missing_keys(client, auth_headers):
    response = client.post(
        "/api/data-sources",
        headers=auth_headers,
        json={"name": "Public R2", "source_type": "r2", "bucket": "bucket", "is_public": True},
    )

    assert response.status_code == 201
    assert "encrypted_access_key_id" not in response.get_json()


def test_turso_ocr_source_starts_background_ingestion(client, auth_headers, monkeypatch):
    project = {"id": "proj_1", "organization_id": "org_1", "owner_user_id": "user_1"}
    started = []

    class FakeProjectRepository:
        def __init__(self, *_args):
            pass

        def get(self, project_id, organization_id):
            assert project_id == "proj_1"
            assert organization_id == "org_1"
            return project

    def fake_start(_app, started_project, source):
        started.append((started_project, source))

    monkeypatch.setattr("backend.app.routes.data_sources.ProjectRepository", FakeProjectRepository)
    monkeypatch.setattr("backend.app.routes.data_sources.start_turso_ocr_ingestion", fake_start)

    response = client.post(
        "/api/data-sources",
        headers=auth_headers,
        json={
            "name": "SC OCR",
            "source_type": "turso_ocr",
            "project_id": "proj_1",
            "turso_database_url": "libsql://ocr-db.turso.io",
            "turso_auth_token": "ocr-token",
            "table_name": "pdfs",
            "id_column": "path",
            "text_column": "ocr_text",
            "batch_size": 100,
            "max_documents": 250,
            "skip_graph_extraction": True,
        },
    )

    assert response.status_code == 201
    body = response.get_json()
    assert body["ingestion_status"] == "pending"
    assert len(started) == 1
    assert started[0][0] == project
    metadata = started[0][1]["prefix"]
    assert '"batch_size": 100' in metadata
    assert '"max_documents": 250' in metadata
    assert '"skip_graph_extraction": true' in metadata
