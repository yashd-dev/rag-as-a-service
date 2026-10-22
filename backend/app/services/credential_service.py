from backend.app.db.repository import SimpleRepository
from backend.app.services.auth_context import AuthContext
from backend.app.services.crypto import SecretBox, mask_secret
from backend.app.services.project_service import ValidationError


class CredentialService:
    def __init__(self, repository: SimpleRepository, secret_box: SecretBox):
        self.repository = repository
        self.secret_box = secret_box

    def create(self, auth: AuthContext, payload: dict) -> dict:
        api_key = str(payload.get("api_key", "")).strip()
        if not api_key:
            raise ValidationError("api_key is required")
        for field in ("name", "provider", "credential_type"):
            if not str(payload.get(field, "")).strip():
                raise ValidationError(f"{field} is required")
        row = self.repository.create(
            {
                "organization_id": auth.organization_id,
                "owner_user_id": auth.user_id,
                "name": payload["name"],
                "provider": payload["provider"],
                "credential_type": payload["credential_type"],
                "encrypted_api_key": self.secret_box.encrypt(api_key),
                "base_url": payload.get("base_url"),
                "default_model": payload.get("default_model"),
                "default_embedding_model": payload.get("default_embedding_model"),
                "is_org_shared": int(bool(payload.get("is_org_shared", False))),
                "is_default": int(bool(payload.get("is_default", False))),
            }
        )
        return self.safe(row, api_key)

    def list(self, auth: AuthContext) -> list[dict]:
        return [
            self.safe(row) for row in self.repository.list_for_org(auth.organization_id)
        ]

    def safe(self, row: dict, plain_secret: str | None = None) -> dict:
        safe_row = dict(row)
        safe_row.pop("encrypted_api_key", None)
        if plain_secret:
            safe_row["api_key_hint"] = mask_secret(plain_secret)
        return safe_row
