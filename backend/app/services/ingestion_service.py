"""Canonical input staging. Vector/graph indexing is deliberately not implied."""

import json
from pathlib import Path

from pypdf import PdfReader

from backend.app.db.connection import db
from backend.app.db.indexing import IdentityConflict, IndexRepository
from backend.app.db.repository import SimpleRepository, now_ms
from backend.app.services.crypto import SecretBox
from backend.app.services.rag import fingerprint
from backend.inventory.report import has_text
from backend.inventory.sql import identifier, open_reader


class IngestionError(Exception):
    pass


class IngestionService:
    def __init__(self, app_config):
        self.config = app_config
        self.index = IndexRepository(app_config)
        self.documents = SimpleRepository(
            app_config["TURSO_DATABASE_URL"],
            app_config["TURSO_AUTH_TOKEN"],
            "documents",
            "doc",
        )

    def register_upload(self, project, file_name, byte_hash, user_id):
        document_id = "doc_" + fingerprint(
            [project["organization_id"], project["id"], "upload", file_name, byte_hash]
        )
        with db(self.index.url, self.index.token) as conn:
            conn.execute(
                "INSERT INTO documents VALUES(?,?,?,?,?,'pending',?,?) ON CONFLICT(id) DO NOTHING",
                (
                    document_id,
                    project["id"],
                    project["organization_id"],
                    user_id,
                    file_name,
                    now_ms(),
                    now_ms(),
                ),
            )
        return self.documents.get(document_id, project["organization_id"])

    def ingest_uploaded_file(self, project, document, file_path: Path):
        try:
            text, metadata = self.extract_text(file_path)
        except Exception as exc:
            # Extraction errors still have a durable generation and safe failure reason.
            self.index.record_failure(project, document, type(exc).__name__)
            raise IngestionError("Text staging failed; see document readiness") from exc
        try:
            return self.ingest_text(
                project, document, text, metadata | {"file_name": document["file_name"]}
            )
        except Exception as exc:
            raise IngestionError("Text staging failed; see document readiness") from exc

    def ingest_text(self, project, document, text, metadata=None):
        self.index.stage(
            project,
            "upload",
            document["id"],
            text,
            metadata,
            file_name=document["file_name"],
            document_id=document["id"],
        )
        return self.documents.get(document["id"], project["organization_id"]) | {
            "readiness": self.index.readiness(project, document["id"]),
        }

    def ingest_text_chunks_only(self, project, document, text):
        return self.ingest_text(project, document, text)

    def extract_text(self, file_path):
        if file_path.suffix.lower() in {".txt", ".md", ".csv", ".json"}:
            return file_path.read_text(encoding="utf-8"), {"format": "text"}
        if file_path.suffix.lower() != ".pdf":
            raise IngestionError("Unsupported document type")
        parts, pages, offset = [], [], 0
        for number, page in enumerate(PdfReader(str(file_path)).pages, 1):
            text = page.extract_text() or ""
            parts.append(text)
            pages.append({"page": number, "start": offset, "end": offset + len(text)})
            offset += len(text) + 2
        text = "\n\n".join(parts)
        if not has_text(text):
            raise IngestionError("PDF has no embedded text; supply existing OCR text")
        return text, {"format": "pdf_embedded_text", "pages": pages}


class TursoOcrIngestionService(IngestionService):
    def __init__(self, app_config):
        super().__init__(app_config)
        self.sources = SimpleRepository(
            app_config["TURSO_DATABASE_URL"],
            app_config["TURSO_AUTH_TOKEN"],
            "data_sources",
            "src",
        )

    def fetch_batch(self, source, metadata, limit, after=None):
        token = SecretBox(self.config["CREDENTIAL_ENCRYPTION_KEY"]).decrypt(
            source["encrypted_secret_access_key"]
        )
        table, id_col = identifier(metadata["table_name"]), identifier(
            metadata["id_column"]
        )
        status_col = identifier(metadata.get("status_column") or "ocr_status")
        where = f"{status_col} = ?"
        params = [metadata.get("status_value") or "done"]
        if after is not None:
            where += f" AND {id_col} > ?"
            params.append(after)
        with open_reader(source["endpoint_url"], token) as reader:
            if after is None:
                counts = reader.query(
                    f"SELECT count(*) AS total, count({id_col}) AS ids, count(DISTINCT {id_col}) AS distinct_ids FROM {table}"
                )[0]
                if not counts["total"] == counts["ids"] == counts["distinct_ids"]:
                    raise IngestionError("Source IDs must be non-null and unique")
            return reader.query(
                f"SELECT * FROM {table} WHERE {where} ORDER BY {id_col} LIMIT ?",
                (*params, limit),
            )

    def run_background_ingestion(self, project, source, dry_run=False):
        metadata = json.loads(source.get("prefix") or "{}")
        if (
            source["organization_id"] != project["organization_id"]
            or metadata.get("project_id") != project["id"]
        ):
            raise IngestionError("Source does not belong to project")
        source_key = "ocr_" + fingerprint(
            [
                source["endpoint_url"].rstrip("/"),
                metadata["table_name"],
                metadata["id_column"],
            ]
        )
        limit = min(max(int(metadata.get("batch_size") or 50), 1), 500)
        max_documents = metadata.get("max_documents")
        # shortcut: replay all eligible source rows per run; add durable keyset scheduling when full scans become costly.
        after, processed, failed, excluded = None, 0, 0, 0
        plans, failures = [], []
        try:
            while max_documents is None or processed < int(max_documents):
                rows = self.fetch_batch(source, metadata, limit, after)
                if not rows:
                    break
                for row in rows:
                    record_id = row[metadata["id_column"]]
                    if record_id is None or record_id == after:
                        raise IngestionError("Source IDs must be non-null and unique")
                    after = record_id
                    text = row[metadata["text_column"]]
                    if not has_text(text):
                        excluded += 1
                        continue
                    processed += 1
                    try:
                        plan = self.index.stage(
                            project,
                            source_key,
                            record_id,
                            text,
                            {
                                "source_type": "turso_ocr",
                                "source_row": {
                                    k: v
                                    for k, v in row.items()
                                    if k != metadata["text_column"]
                                },
                                "source_uri": row.get(
                                    metadata.get("url_column") or "url"
                                ),
                            },
                            file_name=str(record_id),
                            dry_run=dry_run,
                        )
                        plans.append(plan)
                    except Exception as exc:  # noqa: BLE001
                        # Continue the batch with secret-safe per-record failures.
                        failed += 1
                        failures.append(
                            {
                                "record_id_sha256": fingerprint(record_id),
                                "code": type(exc).__name__,
                                "retryable": not isinstance(exc, IdentityConflict),
                            }
                        )
                    if max_documents is not None and processed >= int(max_documents):
                        break
            result = {
                "ingestion_status": (
                    "failed"
                    if failed
                    else (
                        "processing"
                        if any(plan.get("busy") for plan in plans)
                        else "text_ready" if processed else "no_eligible_text"
                    )
                ),
                "processed_count": processed,
                "completed_count": sum(
                    plan.get("state") == "text_ready" for plan in plans
                ),
                "failed_count": failed,
                "excluded_count": excluded,
                "last_source_id": after,
                "dry_run": dry_run,
                "plans": plans,
                "failures": failures,
            }
            if not dry_run:
                self.sources.update(
                    source["id"],
                    source["organization_id"],
                    {
                        "prefix": json.dumps(
                            metadata
                            | {k: v for k, v in result.items() if k != "plans"}
                            | {"ingestion_finished_at": now_ms()}
                        )
                    },
                )
            return result
        except Exception:  # noqa: BLE001
            # Persist safe progress and redact source transport errors.
            if not dry_run:
                self.sources.update(
                    source["id"],
                    source["organization_id"],
                    {
                        "prefix": json.dumps(
                            metadata
                            | {
                                "ingestion_status": "failed",
                                "last_error": "source_read_failed",
                            }
                        )
                    },
                )
            raise IngestionError(
                "Source staging failed; source progress retained"
            ) from None
