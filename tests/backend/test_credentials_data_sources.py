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
