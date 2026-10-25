import json

import httpx
import pytest

from backend.app.db.repository import SimpleRepository
from backend.app.services import generation, llm_client
from backend.app.services.auth_context import AuthContext
from backend.app.services.crypto import SecretBox
from backend.app.services.project_service import ValidationError
from backend.tests import test_query_api

api = test_query_api.api


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/v1", "https://localhost/v1", "https://169.254.169.254/v1",
    "https://key@api.openai.com/v1",
    "https://api.openai.com:8443/v1", "https://api.openai.com/v1?redirect=private",
    "https://api.openai.com/v1/../private", "https://api.openai.com/v1#secret",
])
def test_byok_rejects_unsafe_or_unsupported_endpoint_before_network(url):
    with pytest.raises(ValidationError):
        generation.endpoint(url)


def test_byok_accepts_custom_gateway_endpoint():
    assert generation.endpoint("https://ai-gateway.vercel.sh/v1") == "https://ai-gateway.vercel.sh/v1"


def test_key_validation_is_bounded_no_redirects_and_verifies_model(monkeypatch):
    original = httpx.Client
    calls = []

    def handle(request):
        calls.append(request)
        assert str(request.url) == "https://api.mistral.ai/v1/models"
        assert request.headers["authorization"] == "Bearer fixture-only-key"
        return httpx.Response(200, json={"data": [{"id": "fixture-chat-model"}]})

    def client(**kwargs):
        assert kwargs == {"timeout": 10, "follow_redirects": False, "trust_env": False}
        return original(transport=httpx.MockTransport(handle), **kwargs)

    monkeypatch.setattr(generation.httpx, "Client", client)
    assert generation.validate_key_model("https://api.mistral.ai/v1/", "fixture-only-key", "fixture-chat-model") == "https://api.mistral.ai/v1"
    with pytest.raises(ValidationError, match="Model was not found"):
        generation.validate_key_model("https://api.mistral.ai/v1", "fixture-only-key", "unknown-model")
    assert len(calls) == 2


def test_byok_owner_sharing_revocation_and_foreign_org_permissions(store):
    index, _, _ = store
    config = {"TURSO_DATABASE_URL": index.url, "TURSO_AUTH_TOKEN": index.token, "CREDENTIAL_ENCRYPTION_KEY": "fixture-encryption"}
    repo = SimpleRepository(index.url, index.token, "provider_credentials", "cred")
    row = repo.create({"organization_id": "o", "owner_user_id": "u", "name": "Private model", "provider": "openai", "credential_type": "llm", "encrypted_api_key": SecretBox("fixture-encryption").encrypt("fixture-key"), "base_url": "https://api.openai.com/v1", "default_model": "fixture-chat", "last_validated_at": 1})
    selection = "credential:" + row["id"]
    own = generation.resolve(config, AuthContext("u", "o", "owner"), selection)
    assert own.api_key == "fixture-key" and own.user_supplied
    for auth in (AuthContext("other", "o", "owner"), AuthContext("u", "foreign", "owner")):
        with pytest.raises(generation.SelectionError, match="generation_config_not_found"):
            generation.resolve(config, auth, selection)
    repo.update(row["id"], "o", {"is_org_shared": 1})
    assert generation.resolve(config, AuthContext("other", "o", "member"), selection).model == "fixture-chat"
    repo.update(row["id"], "o", {"status": "revoked"})
    with pytest.raises(generation.SelectionError):
        generation.resolve(config, AuthContext("u", "o", "owner"), selection)


@pytest.mark.parametrize("selection,key,model", [
    ("platform:gemini", "GEMINI_API_KEY", "GEMINI_MODEL"),
    ("platform:mistral", "MISTRAL_API_KEY", "MISTRAL_MODEL"),
    ("byok", None, None),
])
def test_selected_platform_drives_actual_shared_generation_path(api, monkeypatch, selection, key, model):
    app, client, headers, _, _, _, _, _ = api
    if selection == "byok":
        app.config["CREDENTIAL_ENCRYPTION_KEY"] = "fixture-encryption"
        row = generation.credentials(app.config).create({"organization_id": "o", "owner_user_id": "u", "name": "BYOK", "provider": "openai", "credential_type": "llm", "encrypted_api_key": SecretBox("fixture-encryption").encrypt("fixture-selected-secret"), "base_url": "https://api.openai.com/v1", "default_model": "fixture-selected-model", "last_validated_at": 1})
        selection = "credential:" + row["id"]
    else:
        app.config.update({key: "fixture-selected-secret", model: "fixture-selected-model"})
    calls = []

    class Llm:
        def __init__(self, config):
            calls.append(config)
            self.last_model = config.model
            self.client = self

        def complete(self, messages, **kwargs):
            return json.dumps({"status": "answered", "answer": "Evidence [S1]", "used_sources": ["S1"]})

        def close(self):
            pass

    monkeypatch.setattr(llm_client, "OpenAICompatibleLlm", Llm)
    monkeypatch.setattr("backend.app.services.query_service.generate_grounded", llm_client.generate_grounded)
    response = client.post("/api/projects/p/query", headers=headers, json={"message": "question", "mode": "vector", "generation_config": selection})
    assert response.status_code == 200 and response.json["sources"]
    assert calls[0].api_key == "fixture-selected-secret" and calls[0].model == "fixture-selected-model"
    assert response.json["generation"]["configuration"] == selection.removeprefix("platform:")
    assert "fixture-selected-secret" not in response.get_data(as_text=True)
