from backend.app.db.repository import SimpleRepository, now_ms
from backend.app.services.auth_context import AuthContext
from backend.app.services.crypto import SecretBox, mask_secret
from backend.app.services.generation import validate_key_model
from backend.app.services.project_service import ValidationError


class CredentialService:
    def __init__(self, repository: SimpleRepository, secret_box: SecretBox):
        self.repository = repository
        self.secret_box = secret_box

    def create(self, auth: AuthContext, payload: dict) -> dict:
        if not isinstance(payload, dict):
            raise ValidationError("JSON object is required")
        api_key = str(payload.get("api_key", "")).strip()
        if not api_key:
            raise ValidationError("api_key is required")
        for field in ("name", "provider", "credential_type"):
            if not str(payload.get(field, "")).strip():
                raise ValidationError(f"{field} is required")
        if any(field in payload and type(payload[field]) is not bool for field in ("is_org_shared", "is_default")):
            raise ValidationError("Credential sharing/default flags must be boolean")
        base_url = payload.get("base_url")
        if payload["credential_type"] == "llm":
            base_url = validate_key_model(base_url, api_key, payload.get("default_model"))
        row = self.repository.create(
            {
                "organization_id": auth.organization_id,
                "owner_user_id": auth.user_id,
                "name": payload["name"],
                "provider": payload["provider"],
                "credential_type": payload["credential_type"],
                "encrypted_api_key": self.secret_box.encrypt(api_key),
                "base_url": base_url,
                "default_model": payload.get("default_model"),
                "default_embedding_model": payload.get("default_embedding_model"),
                "is_org_shared": int(bool(payload.get("is_org_shared", False))),
                "is_default": int(bool(payload.get("is_default", False))),
                "last_validated_at": now_ms() if payload["credential_type"] == "llm" else None,
            }
        )
        return self.safe(row, api_key)

    def list(self, auth: AuthContext) -> list[dict]:
        return [
            self.safe(row) for row in self.repository.list_for_org(auth.organization_id)
            if row["owner_user_id"] == auth.user_id or row["is_org_shared"]
        ]

    def safe(self, row: dict, plain_secret: str | None = None) -> dict:
        safe_row = dict(row)
        safe_row.pop("encrypted_api_key", None)
        if plain_secret:
            safe_row["api_key_hint"] = mask_secret(plain_secret)
        return safe_row
