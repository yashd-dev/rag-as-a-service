from flask import Blueprint, current_app, jsonify, request

from backend.app.db.repository import SimpleRepository
from backend.app.routes.projects import auth_or_error
from backend.app.services.credential_service import CredentialService
from backend.app.services.crypto import SecretBox
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
