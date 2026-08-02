import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

from main import BUCKET, DB_URL, db, init_db, s3_client
from unstructured_transform import (
    create_parse_job,
    download_output,
    elements_to_text,
    wait_for_job,
)


def pending(limit: int) -> list[Any]:
    with db() as conn:
        return conn.execute(
            """
            SELECT path FROM pdfs
            WHERE (ocr_status != 'done' OR ocr_text IS NULL)
              AND COALESCE(size, 0) <= 50000000
            ORDER BY path
            LIMIT ?
            """,
            (limit,),
        ).fetchall()


def save_result(
    path: str, job_id: str, file_id: str, elements, output_dir: Path
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = path.replace("/", "__")
    (output_dir / f"{safe_name}.json").write_text(json.dumps(elements, indent=2))
    with db() as conn:
        conn.execute(
            """
            UPDATE pdfs
            SET ocr_text = ?, ocr_status = 'done', error = NULL,
                unstructured_job_id = ?, unstructured_file_id = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE path = ?
            """,
            (elements_to_text(elements), job_id, file_id, path),
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


def process_batch(rows: list[Any], output_dir: Path) -> None:
    client = s3_client()
    paths = [row["path"] for row in rows]
    with tempfile.TemporaryDirectory() as tmp:
        local_paths = []
        for path in paths:
            local_path = Path(tmp) / Path(path).name
            client.download_file(BUCKET, path, str(local_path))
            local_paths.append(local_path)

        with db() as conn:
            conn.executemany(
                "UPDATE pdfs SET ocr_status = 'processing', error = NULL WHERE path = ?",
                [(path,) for path in paths],
            )

        job_id = create_parse_job(local_paths)
        job = wait_for_job(job_id)
        output_files = job.get("output_node_files") or []
        if len(output_files) != len(paths):
            raise RuntimeError(
                f"expected {len(paths)} output files, got {len(output_files)}"
            )

        for path, output in zip(paths, output_files, strict=True):
            file_id = output["file_id"]
            elements = download_output(job_id, file_id)
            save_result(path, job_id, file_id, elements, output_dir)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--output-dir", type=Path, default=Path("unstructured-output"))
    args = parser.parse_args()

    if args.batch_size > 10:
        raise SystemExit("--batch-size cannot exceed 10")

    init_db()
    rows = pending(args.limit)
    print(f"database={DB_URL} pending={len(rows)}", flush=True)
    for start in range(0, len(rows), args.batch_size):
        batch = rows[start : start + args.batch_size]
        paths = [row["path"] for row in batch]
        print(f"batch {start // args.batch_size + 1}: {len(batch)} PDFs", flush=True)
        try:
            process_batch(batch, args.output_dir)
        except Exception as exc:
            mark_failed(paths, str(exc))
            raise


if __name__ == "__main__":
    main()
