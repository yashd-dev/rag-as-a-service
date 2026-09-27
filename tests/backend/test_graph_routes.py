class FakeGraphStore:
    def close(self):
        pass

    def project_status(self, project_id, organization_id):
        return {"exists": True, "node_count": 2, "edge_count": 1}

    def project_graph(self, project_id, organization_id):
        return {"nodes": [{"id": "e1", "label": "Article 21"}], "edges": []}


def create_project(client, auth_headers):
    return client.post("/api/projects", headers=auth_headers, json={"name": "Corpus"}).get_json()


def test_graph_status_route(client, auth_headers, monkeypatch):
    project = create_project(client, auth_headers)
    monkeypatch.setattr("backend.app.routes.graph.graph_store", lambda: FakeGraphStore())

    response = client.get(f"/api/projects/{project['id']}/graph/status", headers=auth_headers)

    assert response.status_code == 200
    assert response.get_json()["node_count"] == 2


def test_graph_html_route(client, auth_headers, monkeypatch):
    project = create_project(client, auth_headers)
    monkeypatch.setattr("backend.app.routes.graph.graph_store", lambda: FakeGraphStore())

    response = client.get(f"/api/projects/{project['id']}/graph", headers=auth_headers)

    assert response.status_code == 200
    assert "Article 21" in response.get_data(as_text=True)
