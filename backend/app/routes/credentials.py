from flask import Blueprint, current_app, jsonify, request

from backend.app.db.repository import SimpleRepository, now_ms
from backend.app.routes.projects import auth_or_error
from backend.app.services.credential_service import CredentialService
from backend.app.services.crypto import SecretBox
from backend.app.services.generation import list_configs, validate_key_model
from backend.app.services.project_service import ValidationError

credentials_bp = Blueprint("credentials", __name__)


def service() -> CredentialService:
    repo = SimpleRepository(
        current_app.config["TURSO_DATABASE_URL"],
        current_app.config["TURSO_AUTH_TOKEN"],
        "provider_credentials",
        "cred",
    )
    return CredentialService(
        repo, SecretBox(current_app.config["CREDENTIAL_ENCRYPTION_KEY"])
    )


@credentials_bp.post("")
def create_credential():
    auth, error = auth_or_error()
    if error:
        return error
    try:
        return jsonify(service().create(auth, request.get_json(silent=True) or {})), 201
    except (ValidationError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400


@credentials_bp.get("")
def list_credentials():
    auth, error = auth_or_error()
    if error:
        return error
    return jsonify({"items": service().list(auth)})


@credentials_bp.get("/generation-configs")
def generation_configs():
    auth, error = auth_or_error()
    if error:
        return error
    return jsonify({"items": list_configs(current_app.config, auth)})


@credentials_bp.post("/<credential_id>/validate")
def validate_credential(credential_id):
    auth, error = auth_or_error()
    if error:
        return error
    instance = service()
    row = instance.repository.get(credential_id, auth.organization_id)
    if not row or row["owner_user_id"] != auth.user_id or row["credential_type"] != "llm":
        return jsonify({"error": "Credential not found"}), 404
    try:
        base = validate_key_model(row["base_url"], instance.secret_box.decrypt(row["encrypted_api_key"]), row["default_model"])
    except (ValidationError, ValueError):
        return jsonify({"error": "Provider validation failed"}), 400
    return jsonify(instance.safe(instance.repository.update(credential_id, auth.organization_id, {"base_url": base, "last_validated_at": now_ms()})))


@credentials_bp.delete("/<credential_id>")
def revoke_credential(credential_id):
    auth, error = auth_or_error()
    if error:
        return error
    instance = service()
    row = instance.repository.get(credential_id, auth.organization_id)
    if not row or row["owner_user_id"] != auth.user_id:
        return jsonify({"error": "Credential not found"}), 404
    instance.repository.update(credential_id, auth.organization_id, {"status": "revoked"})
    return "", 204
