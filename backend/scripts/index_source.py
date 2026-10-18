"""Stage existing OCR text. Default dry-run never updates source/application data."""

import argparse
import json
import os
from pathlib import Path

from dotenv import dotenv_values

from backend.app.services.ingestion_service import TursoOcrIngestionService
from backend.inventory.sql import open_reader


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path("backend/.env"))
    parser.add_argument("--organization-id", required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    config = dict(os.environ) | {k: v for k, v in dotenv_values(args.env_file).items() if v is not None}
    config["TURSO_DATABASE_URL"] = config.get("TURSO_DATABASE_URL") or config.get("TURSO_CONNECTION_URL", "")
    with open_reader(config["TURSO_DATABASE_URL"], config["TURSO_AUTH_TOKEN"]) as reader:
        projects = reader.query("SELECT * FROM projects WHERE id=? AND organization_id=?", (args.project_id, args.organization_id))
        sources = reader.query("SELECT * FROM data_sources WHERE id=? AND organization_id=? AND source_type='turso_ocr'", (args.source_id, args.organization_id))
    if not projects or not sources:
        parser.error("Project/source not found in organization")
    result = TursoOcrIngestionService(config).run_background_ingestion(projects[0], sources[0], dry_run=not args.apply)
    print(json.dumps(result))
    return 2 if result["failed_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
