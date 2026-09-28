def test_projects_require_internal_secret(client, auth_headers):
    headers = auth_headers | {"X-Internal-Secret": "bad"}

    response = client.get("/api/projects", headers=headers)

    assert response.status_code == 401


def test_create_and_list_project(client, auth_headers):
    response = client.post(
        "/api/projects",
        headers=auth_headers,
        json={"name": "Supreme Court Corpus", "description": "Judgments"},
    )

    assert response.status_code == 201
    created = response.get_json()
    assert created["organization_id"] == "org_1"
    assert created["owner_user_id"] == "user_1"
    assert created["slug"] == "supreme-court-corpus"
    assert created["embedding_provider"] == "huggingface"
    assert created["embedding_model"] == "google/embeddinggemma-300m"

    list_response = client.get("/api/projects", headers=auth_headers)
    assert list_response.status_code == 200
    items = list_response.get_json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == created["id"]


def test_project_access_is_limited_to_organization(client, auth_headers):
    created = client.post(
        "/api/projects",
        headers=auth_headers,
        json={"name": "Private Corpus"},
    ).get_json()

    other_org_headers = auth_headers | {"X-Organization-Id": "org_2"}
    response = client.get(f"/api/projects/{created['id']}", headers=other_org_headers)

    assert response.status_code == 404


def test_duplicate_project_slug_conflicts(client, auth_headers):
    payload = {"name": "Same Name"}
    assert (
        client.post("/api/projects", headers=auth_headers, json=payload).status_code
        == 201
    )

    response = client.post("/api/projects", headers=auth_headers, json=payload)

    assert response.status_code == 409


def test_create_project_always_uses_embeddinggemma(client, auth_headers):
    response = client.post(
        "/api/projects",
        headers=auth_headers,
        json={
            "name": "Embedding Corpus",
            "embedding_provider": "huggingface",
            "embedding_model": "nomic-ai/nomic-embed-text-v1",
        },
    )

    assert response.status_code == 201
    assert response.get_json()["embedding_model"] == "google/embeddinggemma-300m"


def test_create_project_normalizes_embeddinggemma_short_name(client, auth_headers):
    response = client.post(
        "/api/projects",
        headers=auth_headers,
        json={"name": "Gemma Corpus", "embedding_model": "embeddinggemma-300m"},
    )

    assert response.status_code == 201
    assert response.get_json()["embedding_model"] == "google/embeddinggemma-300m"


def test_create_project_ignores_other_embedding_model_selection(client, auth_headers):
    response = client.post(
        "/api/projects",
        headers=auth_headers,
        json={"name": "Bad Corpus", "embedding_model": "unknown/model"},
    )

    assert response.status_code == 201
    assert response.get_json()["embedding_model"] == "google/embeddinggemma-300m"


def test_delete_project(client, auth_headers):
    created = client.post(
        "/api/projects",
        headers=auth_headers,
        json={"name": "Delete Me"},
    ).get_json()

    delete_response = client.delete(
        f"/api/projects/{created['id']}", headers=auth_headers
    )
    get_response = client.get(f"/api/projects/{created['id']}", headers=auth_headers)

    assert delete_response.status_code == 204
    assert get_response.status_code == 404
