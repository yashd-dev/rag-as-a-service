"""Authorized answer configurations; embedding provenance is deliberately separate."""

from urllib.parse import urlsplit

import httpx

from backend.app.db.repository import SimpleRepository
from backend.app.services.crypto import SecretBox
from backend.app.services.llm_client import LlmConfig, platform_llm_config
from backend.app.services.project_service import ValidationError

SUPPORTED_BASES = {
    "api.openai.com": "/v1",
    "api.mistral.ai": "/v1",
    "generativelanguage.googleapis.com": "/v1beta/openai",
    "openrouter.ai": "/api/v1",
    "api.groq.com": "/openai/v1",
}


class SelectionError(RuntimeError):
    def __init__(self, code, status=400):
        super().__init__(code)
        self.code, self.status = code, status


def endpoint(value):
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https" or parsed.hostname not in SUPPORTED_BASES
            or parsed.port not in (None, 443) or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path.rstrip("/") != SUPPORTED_BASES[parsed.hostname]
            or any(char.isspace() for char in value)
        ):
            raise ValueError
    except (TypeError, ValueError, AttributeError):
        raise ValidationError("Use a supported HTTPS provider base URL: OpenAI, Mistral, Gemini, OpenRouter or Groq") from None
    # Exact provider origins/base paths avoid custom-host SSRF and DNS rebinding.
    return "https://" + parsed.hostname + SUPPORTED_BASES[parsed.hostname]


def validate_key_model(base_url, api_key, model):
    base_url = endpoint(base_url)
    if not isinstance(model, str) or not model.strip() or len(model) > 200:
        raise ValidationError("A supported provider model ID is required")
    try:
        with httpx.Client(timeout=10, follow_redirects=False, trust_env=False) as client:
            response = client.get(base_url + "/models", headers={"Authorization": "Bearer " + api_key})
            response.raise_for_status()
            data = response.json()
            models = data.get("data", []) if isinstance(data, dict) else data if isinstance(data, list) else []
            if not any(row.get("id") == model for row in models if isinstance(row, dict)):
                raise ValidationError("Model was not found in the provider's authorized model list")
    except (httpx.HTTPError, ValueError, AttributeError, TypeError):
        raise ValidationError("Could not validate provider key/model; check credentials and provider availability") from None
    return base_url


def platform_configs(config):
    return {
        "platform:default": platform_llm_config(config),
        "platform:gemini": LlmConfig("https://generativelanguage.googleapis.com/v1beta/openai", config.get("GEMINI_API_KEY", ""), config.get("GEMINI_MODEL", ""), "gemini"),
        "platform:mistral": LlmConfig("https://api.mistral.ai/v1", config.get("MISTRAL_API_KEY", ""), config.get("MISTRAL_MODEL", ""), "mistral"),
    }


def credentials(config):
    return SimpleRepository(config["TURSO_DATABASE_URL"], config["TURSO_AUTH_TOKEN"], "provider_credentials", "cred")


def permitted(row, auth):
    return row and row["status"] == "active" and row["credential_type"] == "llm" and (row["owner_user_id"] == auth.user_id or bool(row["is_org_shared"]))


def list_configs(config, auth):
    result = [
        {"id": key, "name": {"platform:default": "Platform default", "platform:gemini": "Platform Gemini", "platform:mistral": "Platform Mistral"}[key], "model": item.model, "available": bool(item.api_key and item.model)}
        for key, item in platform_configs(config).items()
    ]
    result.extend(
        {"id": "credential:" + row["id"], "name": row["name"] + " (BYOK)", "model": row["default_model"] or "", "available": bool(row["last_validated_at"] and row["default_model"])}
        for row in credentials(config).list_for_org(auth.organization_id) if permitted(row, auth)
    )
    return result


def resolve(config, auth, selection):
    if not isinstance(selection, str):
        raise SelectionError("invalid_generation_config")
    platforms = platform_configs(config)
    if selection in platforms:
        item = platforms[selection]
        if not item.api_key or not item.model:
            raise SelectionError("generation_not_configured", 503)
        return item
    if not selection.startswith("credential:"):
        raise SelectionError("generation_config_not_found", 404)
    row = credentials(config).get(selection.removeprefix("credential:"), auth.organization_id)
    if not permitted(row, auth):
        raise SelectionError("generation_config_not_found", 404)
    if not row["last_validated_at"]:
        raise SelectionError("credential_validation_required", 409)
    try:
        base_url = endpoint(row["base_url"])
        key = SecretBox(config["CREDENTIAL_ENCRYPTION_KEY"]).decrypt(row["encrypted_api_key"])
    except (ValidationError, ValueError):
        raise SelectionError("credential_validation_required", 409) from None
    return LlmConfig(base_url, key, row["default_model"], selection, user_supplied=True)
