def create_project(client, auth_headers):
    return client.post("/api/projects", headers=auth_headers, json={"name": "Corpus"}).get_json()


def test_document_upload_skeleton_is_project_scoped(client, auth_headers):
    project = create_project(client, auth_headers)
    response = client.post(
        f"/api/projects/{project['id']}/documents/upload",
        headers=auth_headers,
        json={"file_name": "judgment.pdf"},
    )

    assert response.status_code == 201
    assert response.get_json()["project_id"] == project["id"]

    other_headers = auth_headers | {"X-Organization-Id": "org_2"}
    denied = client.get(f"/api/projects/{project['id']}/documents", headers=other_headers)
    assert denied.status_code == 404


def test_query_route_logs_run(client, auth_headers):
    project = create_project(client, auth_headers)
    response = client.post(
        f"/api/projects/{project['id']}/query",
        headers=auth_headers,
        json={"message": "What is Article 21?", "mode": "hybrid"},
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["mode"] == "hybrid"
    assert body["query_run_id"].startswith("qry_")


def test_conversation_create(client, auth_headers):
    project = create_project(client, auth_headers)
    response = client.post(
        f"/api/projects/{project['id']}/conversations",
        headers=auth_headers,
        json={"title": "Research"},
    )

    assert response.status_code == 201
    assert response.get_json()["title"] == "Research"
