import json

from backend.app.db.repository import SimpleRepository
from backend.app.services.auth_context import AuthContext
from backend.app.services.crypto import SecretBox, mask_secret
from backend.app.services.project_service import ValidationError


def payload_bool(payload: dict, key: str, default: bool = False) -> bool:
    value = payload.get(key, default)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


class DataSourceService:
    def __init__(self, repository: SimpleRepository, secret_box: SecretBox):
        self.repository = repository
        self.secret_box = secret_box

    def create(self, auth: AuthContext, payload: dict) -> dict:
        for field in ("name", "source_type"):
            if not str(payload.get(field, "")).strip():
                raise ValidationError(f"{field} is required")
        if payload["source_type"] == "turso_ocr":
            for field in ("turso_database_url", "turso_auth_token", "table_name", "id_column", "text_column"):
                if not str(payload.get(field, "")).strip():
                    raise ValidationError(f"{field} is required")
            batch_size = min(max(int(payload.get("batch_size") or 50), 1), 500)
            max_documents = int(payload["max_documents"]) if str(payload.get("max_documents", "")).strip() else None
            if max_documents is not None and max_documents < 1:
                raise ValidationError("max_documents must be greater than 0")
            metadata = {
                "project_id": payload.get("project_id"),
                "table_name": payload["table_name"],
                "id_column": payload["id_column"],
                "text_column": payload["text_column"],
                "status_column": payload.get("status_column") or "ocr_status",
                "status_value": payload.get("status_value") or "done",
                "url_column": payload.get("url_column") or "url",
                "batch_size": batch_size,
                "max_documents": max_documents,
                "skip_graph_extraction": payload_bool(payload, "skip_graph_extraction", False),
                "ingestion_status": "pending",
                "ingestion_started_at": None,
                "ingestion_finished_at": None,
                "last_source_id": None,
                "processed_count": 0,
                "completed_count": 0,
                "failed_count": 0,
                "last_error": None,
            }
            row = self.repository.create(
                {
                    "organization_id": auth.organization_id,
                    "owner_user_id": auth.user_id,
                    "name": payload["name"],
                    "source_type": payload["source_type"],
                    "bucket": payload["table_name"],
                    "endpoint_url": payload["turso_database_url"],
                    "public_base_url": None,
                    "prefix": json.dumps(metadata),
                    "encrypted_access_key_id": None,
                    "encrypted_secret_access_key": self.secret_box.encrypt(payload["turso_auth_token"]),
                    "region": None,
                    "is_public": 0,
                }
            )
            return self.safe(row)
        if not str(payload.get("bucket", "")).strip():
            raise ValidationError("bucket is required")
        is_public = bool(payload.get("is_public", False))
        access_key = str(payload.get("access_key_id", "")).strip()
        secret_key = str(payload.get("secret_access_key", "")).strip()
        if not is_public and (not access_key or not secret_key):
            raise ValidationError("access_key_id and secret_access_key are required")
        row = self.repository.create(
            {
                "organization_id": auth.organization_id,
                "owner_user_id": auth.user_id,
                "name": payload["name"],
                "source_type": payload["source_type"],
                "bucket": payload["bucket"],
                "endpoint_url": payload.get("endpoint_url"),
                "public_base_url": payload.get("public_base_url"),
                "prefix": payload.get("prefix"),
                "encrypted_access_key_id": self.secret_box.encrypt(access_key) if access_key else None,
                "encrypted_secret_access_key": self.secret_box.encrypt(secret_key) if secret_key else None,
                "region": payload.get("region"),
                "is_public": int(is_public),
            }
        )
        return self.safe(row, access_key)

    def list(self, auth: AuthContext) -> list[dict]:
        return [self.safe(row) for row in self.repository.list_for_org(auth.organization_id)]

    def safe(self, row: dict, plain_access_key: str | None = None) -> dict:
        safe_row = dict(row)
        safe_row.pop("encrypted_access_key_id", None)
        safe_row.pop("encrypted_secret_access_key", None)
        metadata = json.loads(str(safe_row.get("prefix") or "{}")) if safe_row.get("source_type") == "turso_ocr" else {}
        for key in (
            "ingestion_status",
            "ingestion_started_at",
            "ingestion_finished_at",
            "last_source_id",
            "processed_count",
            "completed_count",
            "failed_count",
            "last_error",
            "batch_size",
            "max_documents",
            "skip_graph_extraction",
            "project_id",
        ):
            if key in metadata:
                safe_row[key] = metadata[key]
        if plain_access_key:
            safe_row["access_key_id_hint"] = mask_secret(plain_access_key)
        return safe_row
