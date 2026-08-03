# Dataset API

FastAPI service that indexes PDFs from S3/R2 into Turso and stores parsed text from Unstructured Transform.

## Run

```bash
uv sync
TURSO_DATABASE_URL=libsql://... TURSO_AUTH_TOKEN=... R2_BUCKET=your-bucket R2_ENDPOINT_URL=https://...r2.cloudflarestorage.com uv run fastapi dev main.py
```

For public AWS S3 testing, omit credentials and set `R2_BUCKET=indian-supreme-court-judgments`.

## Docker

```bash
docker build -t dataset-api .
docker run --rm -p 8000:8000 --env-file .env dataset-api
```

Startup sync and OCR run inside the container by default. Set `SYNC_ON_STARTUP=false` or `PARSE_ON_STARTUP=false` to skip them.

For Railway, set these as service variables. Build args also exist in the Dockerfile, but do not put secrets in build args unless you accept them being baked into the image.

For an overnight Railway worker/job that syncs and OCRs everything, set `WORKER=true`. It runs `init_db()`, S3 sync, all pending OCR batches, then exits. Keep `STARTUP_BATCH_SIZE=10` for max Unstructured batch size.

## Env

- `R2_BUCKET`: bucket name. Required.
- `R2_ENDPOINT_URL`: S3-compatible endpoint. Optional for AWS S3.
- `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`: credentials. Optional for public buckets. `CLOUDFLARE_R2_*` and AWS env names also work.
- `PDF_PREFIX`: object prefix. Default `sc-documents/data/pdf/`. Keep it at this parent path so new `year=YYYY/...` folders are picked up automatically.
- `PUBLIC_BASE_URL`: public URL prefix. Default `https://{bucket}.s3.amazonaws.com`.
- `TURSO_DATABASE_URL`: Turso database URL. Required.
- `TURSO_AUTH_TOKEN`: Turso auth token. Required for protected databases.
- `SYNC_ON_STARTUP`: set `false` to skip startup sync. Default `true`.
- `PARSE_ON_STARTUP`: set `false` to let the API start before all PDFs are parsed. Default `true`.
- `STARTUP_BATCH_SIZE`: Unstructured PDFs per startup job. Clamped to `1..10`, default `10`.
- `HTTP_TIMEOUT`: default socket timeout for Turso/R2 HTTP calls. Default `30` seconds.
- `WORKER`: set `true` to run sync/OCR as a one-shot worker instead of serving the API. Default `false`.
- `UNSTRUCTURED_API_URL`: Transform API URL. Default from Unstructured docs: `https://platform-api.transform.unstructured.io/api/v1`.
- `UNSTRUCTURED_API_KEY`: Transform API key.
- `UNSTRUCTURED_POLL_SECONDS`: job polling interval. Default `10`.
- `UNSTRUCTURED_PARTITION_STRATEGY`: `fast` for PDFs with embedded text, `hi_res` for OCR, `vlm` for best-quality vision parsing. Default `fast`.

Startup sync and OCR run in the background so hosts like Railway can mark the API healthy. Progress prints to stdout: pending count, batch number, per-file download/save, Unstructured job status, and total completed.

## Bulk Parse

```bash
uv run python bulk_unstructured_parse.py --limit 50 --batch-size 10
```

Each batch downloads PDFs from S3/R2 to a temp directory, creates one Unstructured Transform job, downloads JSON outputs to `unstructured-output/`, and stores extracted text in `pdfs.ocr_text`.

## Endpoints

- `GET /pdfs?limit=100&offset=0`: PDF inventory.
- `POST /pdfs/{path}/ocr?force=false`: download one PDF, parse it with Unstructured, save text.
- `GET /contents?limit=20&offset=0`: paginated paths and OCR text.
- `POST /sync?force=false`: sync S3/R2 PDF list into DB.
