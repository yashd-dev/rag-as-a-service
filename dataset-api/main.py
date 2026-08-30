import asyncio
import json
import os
import socket
import tempfile
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Annotated, Any

import boto3
import turso_serverless
from botocore import UNSIGNED
from botocore.client import Config
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query

from unstructured_transform import (
    create_parse_job,
    download_output,
    elements_to_text,
    require_config,
    wait_for_job,
)

load_dotenv()

socket.setdefaulttimeout(float(os.getenv("HTTP_TIMEOUT", "30")))

DB_URL = os.getenv("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN")
BUCKET = os.getenv("R2_BUCKET") or os.getenv("AWS_BUCKET") or os.getenv("S3_BUCKET")
ENDPOINT_URL = os.getenv("R2_ENDPOINT_URL") or os.getenv("AWS_ENDPOINT_URL_S3")
PDF_PREFIX = os.getenv("PDF_PREFIX", "sc-documents/data/pdf/")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL")
PARSE_ON_STARTUP = os.getenv("PARSE_ON_STARTUP", "true").lower() != "false"
STARTUP_BATCH_SIZE = int(os.getenv("STARTUP_BATCH_SIZE", "10"))
QNA_DIR = Path(__file__).parent / "qna"
TEST_DATASET_PATH = QNA_DIR / "dataset.json"
TEST_ANSWERS_PATH = QNA_DIR / "qna.json"


@contextmanager
def db():
    if not DB_URL:
        raise RuntimeError("TURSO_DATABASE_URL is not set")
    conn = turso_serverless.connect(DB_URL, auth_token=TURSO_AUTH_TOKEN)
    conn.row_factory = turso_serverless.Row
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_db() -> None:
    with db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pdfs (
                path TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                size INTEGER,
                etag TEXT,
                last_modified TEXT,
                ocr_text TEXT,
                ocr_status TEXT NOT NULL DEFAULT 'pending',
                page_count INTEGER,
                error TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        columns = {row[1] for row in conn.execute("PRAGMA table_info(pdfs)")}
        for name in ("unstructured_job_id", "unstructured_file_id"):
            if name not in columns:
                conn.execute(f"ALTER TABLE pdfs ADD COLUMN {name} TEXT")


def s3_client():
    if not BUCKET:
        raise HTTPException(500, "R2_BUCKET is not set")
    access_key = (
        os.getenv("R2_ACCESS_KEY_ID")
        or os.getenv("CLOUDFLARE_R2_ACCESS_KEY_ID")
        or os.getenv("AWS_ACCESS_KEY_ID")
    )
    secret_key = (
        os.getenv("R2_SECRET_ACCESS_KEY")
        or os.getenv("CLOUDFLARE_R2_SECRET_ACCESS_KEY")
        or os.getenv("AWS_SECRET_ACCESS_KEY")
    )
    if access_key and secret_key:
        return boto3.client(
            "s3",
            endpoint_url=ENDPOINT_URL,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )
    return boto3.client(
        "s3", endpoint_url=ENDPOINT_URL, config=Config(signature_version=UNSIGNED)
    )


def object_url(path: str) -> str:
    base = PUBLIC_BASE_URL or f"https://{BUCKET}.s3.amazonaws.com"
    return f"{base.rstrip('/')}/{path}"


def load_json_file(path: Path) -> Any:
    if not path.exists():
        raise HTTPException(404, f"File not found: {path.name}")
    return json.loads(path.read_text(encoding="utf-8"))


def paginate_items(items: list[Any], limit: int, offset: int) -> dict[str, Any]:
    page = items[offset : offset + limit]
    total = len(items)
    return {
        "total": total,
        "count": len(page),
        "limit": limit,
        "offset": offset,
        "pages_left": max((total - offset - len(page) + limit - 1) // limit, 0),
        "items": page,
    }


def load_qna_items(path: Path) -> list[dict[str, Any]]:
    payload = load_json_file(path)
    if not isinstance(payload, dict):
        raise HTTPException(500, "qna.json must be an object")

    items = []
    for key in sorted(payload, key=lambda value: int(value)):
        row = payload[key]
        if not isinstance(row, dict):
            continue
        items.append({"id": int(key), **row})
    return items


def sync_pdfs(force: bool = False) -> dict:
    with db() as conn:
        if not force and conn.execute("SELECT 1 FROM pdfs LIMIT 1").fetchone():
            total = conn.execute("SELECT COUNT(*) FROM pdfs").fetchone()[0]
            return {"synced": False, "total": total, "inserted": 0}

    client = s3_client()
    inserted = 0
    seen = 0
    paginator = client.get_paginator("list_objects_v2")
    with db() as conn:
        for page in paginator.paginate(Bucket=BUCKET, Prefix=PDF_PREFIX):
            for obj in page.get("Contents", []):
                path = obj["Key"]
                if not path.lower().endswith(".pdf"):
                    continue
                seen += 1
                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO pdfs(path, url, size, etag, last_modified)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        path,
                        object_url(path),
                        obj.get("Size"),
                        obj.get("ETag", "").strip('"'),
                        obj.get("LastModified").isoformat()
                        if obj.get("LastModified")
                        else None,
                    ),
                )
                inserted += cursor.rowcount
        total = conn.execute("SELECT COUNT(*) FROM pdfs").fetchone()[0]
    return {"synced": True, "total": total, "inserted": inserted, "seen": seen}


def missing_pdfs() -> list[Any]:
    with db() as conn:
        return conn.execute(
            """
            SELECT path FROM pdfs
            WHERE ocr_status != 'done' OR ocr_text IS NULL
            ORDER BY path
            """
        ).fetchall()


def mark_processing(paths: list[str]) -> None:
    with db() as conn:
        conn.executemany(
            "UPDATE pdfs SET ocr_status = 'processing', error = NULL WHERE path = ?",
            [(path,) for path in paths],
        )


def mark_failed(paths: list[str], error: str) -> None:
    with db() as conn:
        conn.executemany(
            """
            UPDATE pdfs
            SET ocr_status = 'failed', error = ?, updated_at = CURRENT_TIMESTAMP
            WHERE path = ?
            """,
            [(error, path) for path in paths],
        )


def save_parse(path: str, text: str, job_id: str, file_id: str) -> dict:
    with db() as conn:
        conn.execute(
            """
            UPDATE pdfs
            SET ocr_text = ?, page_count = NULL, ocr_status = 'done',
                error = NULL, unstructured_job_id = ?, unstructured_file_id = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE path = ?
            """,
            (text, job_id, file_id, path),
        )
        updated = conn.execute("SELECT * FROM pdfs WHERE path = ?", (path,)).fetchone()
    return dict(updated)


def parse_pdf_batch(
    rows: list[Any], batch_index: int, total_batches: int
) -> None:
    client = s3_client()
    paths = [row["path"] for row in rows]
    print(
        f"Unstructured batch {batch_index}/{total_batches}: {len(paths)} PDFs",
        flush=True,
    )
    with tempfile.TemporaryDirectory() as tmp:
        local_paths = []
        for index, path in enumerate(paths, start=1):
            local_path = Path(tmp) / Path(path).name
            print(f"  download {index}/{len(paths)} {path}", flush=True)
            client.download_file(BUCKET, path, str(local_path))
            local_paths.append(local_path)

        mark_processing(paths)
        job_id = create_parse_job(local_paths)
        print(f"  job {job_id} submitted", flush=True)
        job = wait_for_job(job_id)
        outputs = job.get("output_node_files") or []
        if len(outputs) != len(paths):
            raise RuntimeError(
                f"expected {len(paths)} output files, got {len(outputs)}"
            )

        for index, (path, output) in enumerate(
            zip(paths, outputs, strict=True), start=1
        ):
            print(f"  save {index}/{len(paths)} {path}", flush=True)
            file_id = output["file_id"]
            elements = download_output(job_id, file_id)
            save_parse(path, elements_to_text(elements), job_id, file_id)


def parse_missing_pdfs() -> dict:
    rows = missing_pdfs()
    if not rows:
        print("Unstructured startup parse: 0 pending PDFs", flush=True)
        return {"parsed": 0}

    batch_size = min(max(STARTUP_BATCH_SIZE, 1), 10)
    total_batches = (len(rows) + batch_size - 1) // batch_size
    print(
        f"Unstructured startup parse: {len(rows)} pending PDFs, "
        f"{total_batches} batches of up to {batch_size}",
        flush=True,
    )
    parsed = 0
    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]
        try:
            parse_pdf_batch(batch, start // batch_size + 1, total_batches)
        except Exception as exc:
            paths = [row["path"] for row in batch]
            mark_failed(paths, str(exc))
            raise
        parsed += len(batch)
        print(f"Unstructured progress: {parsed}/{len(rows)} PDFs done", flush=True)
    return {"parsed": parsed}


def run_startup_jobs() -> None:
    if os.getenv("SYNC_ON_STARTUP", "true").lower() != "false":
        print("Startup sync: begin", flush=True)
        sync_pdfs(force=True)
        print("Startup sync: done", flush=True)
    if PARSE_ON_STARTUP:
        print("Startup OCR: begin", flush=True)
        require_config()
        parse_missing_pdfs()
        print("Startup OCR: done", flush=True)


def startup_jobs() -> None:
    try:
        run_startup_jobs()
    except Exception as exc:  # noqa: BLE001
        print(f"Startup job failed: {exc}", flush=True)


def run_worker() -> None:
    init_db()
    run_startup_jobs()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if os.getenv("SYNC_ON_STARTUP", "true").lower() != "false" or PARSE_ON_STARTUP:
        asyncio.create_task(asyncio.to_thread(startup_jobs))
    yield


app = FastAPI(title="Dataset API", lifespan=lifespan)


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/sync")
def sync(force: bool = False):
    return sync_pdfs(force=force)


@app.get("/pdfs")
def list_pdfs(
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    with db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM pdfs").fetchone()[0]
        rows = conn.execute(
            """
            SELECT path, url, size, last_modified, ocr_status, page_count
            FROM pdfs ORDER BY path LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
    return {
        "total": total,
        "count": len(rows),
        "limit": limit,
        "offset": offset,
        "pages_left": max((total - offset - len(rows) + limit - 1) // limit, 0),
        "items": [dict(row) for row in rows],
    }


@app.post("/pdfs/{path:path}/ocr")
def extract_pdf(path: str, force: bool = False):
    with db() as conn:
        row = conn.execute("SELECT * FROM pdfs WHERE path = ?", (path,)).fetchone()
        if not row:
            raise HTTPException(404, "PDF path not found")
        if row["ocr_text"] and not force:
            return dict(row)
        conn.execute(
            "UPDATE pdfs SET ocr_status = 'processing', error = NULL WHERE path = ?",
            (path,),
        )

    try:
        client = s3_client()
        with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
            client.download_file(BUCKET, path, f.name)
            job_id = create_parse_job([Path(f.name)])
            job = wait_for_job(job_id)
            file_id = (job.get("output_node_files") or [])[0]["file_id"]
            elements = download_output(job_id, file_id)
            text = elements_to_text(elements)
    except Exception as exc:
        with db() as conn:
            conn.execute(
                """
                UPDATE pdfs
                SET ocr_status = 'failed', error = ?, updated_at = CURRENT_TIMESTAMP
                WHERE path = ?
                """,
                (str(exc), path),
            )
        raise HTTPException(500, f"OCR failed: {exc}") from exc

    return save_parse(path, text, job_id, file_id)


@app.get("/contents")
def list_contents(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    include_pending: bool = False,
):
    where = "" if include_pending else "WHERE ocr_status = 'done'"
    with db() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM pdfs {where}").fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT path, url, ocr_text, ocr_status, page_count
            FROM pdfs {where} ORDER BY path LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
    return {
        "total": total,
        "count": len(rows),
        "limit": limit,
        "offset": offset,
        "pages_left": max((total - offset - len(rows) + limit - 1) // limit, 0),
        "items": [dict(row) for row in rows],
    }


@app.get("/test/data")
def test_data(
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    payload = load_json_file(TEST_DATASET_PATH)
    items = payload.get("items")
    if not isinstance(items, list):
        raise HTTPException(500, "dataset.json missing items array")
    return {
        "generated_at": payload.get("generated_at"),
        "source_dir": payload.get("source_dir"),
        **paginate_items(items, limit, offset),
    }


@app.get("/test/answers")
def test_answers(
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return paginate_items(load_qna_items(TEST_ANSWERS_PATH), limit, offset)
