"""Operator-only registration of existing legal data; read-only unless --apply."""

import argparse
import os
from pathlib import Path

from dotenv import dotenv_values

from backend.app.db.connection import connect
from backend.inventory.sql import Reader, open_reader
from backend.scripts.migrate import backup


def inspect(reader, organization_id, project_id):
    rows = reader.query(
        "SELECT id FROM projects WHERE id=? AND organization_id=?",
        (project_id, organization_id),
    )
    if not rows:
        raise ValueError("Canonical project not found in the specified organization")
    if reader.query(
        "SELECT 1 FROM project_corpus_references WHERE project_id=?", (project_id,)
    ):
        raise ValueError("A reference cannot be registered as the canonical corpus")
    existing = reader.query("SELECT project_id FROM shared_corpora WHERE id='legal'")
    if existing and existing[0]["project_id"] != project_id:
        raise ValueError("Legal corpus is already registered to a different project")
    return bool(existing)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path("backend/.env"))
    parser.add_argument("--organization-id", required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", type=Path)
    args = parser.parse_args(argv)
    if args.apply and not args.backup:
        parser.error(
            "--apply requires a new --backup path; stop application writers first"
        )
    env = dict(os.environ) | {
        k: v for k, v in dotenv_values(args.env_file).items() if v is not None
    }
    url = env.get("TURSO_DATABASE_URL") or env.get("TURSO_CONNECTION_URL", "")
    token = env.get("TURSO_AUTH_TOKEN", "")
    if not args.apply:
        with open_reader(url, token) as reader:
            registered = inspect(reader, args.organization_id, args.project_id)
        print(
            "Already registered; no change"
            if registered
            else "Read-only plan: register this existing project as the shared legal corpus; no source/index writes"
        )
        return
    conn = connect(url, token)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("BEGIN IMMEDIATE")
        reader = Reader(conn)
        if inspect(reader, args.organization_id, args.project_id):
            conn.rollback()
            print("Already registered; no change")
            return
        backup(reader, args.backup)
        conn.execute(
            "INSERT INTO shared_corpora(id,project_id) VALUES('legal',?)",
            (args.project_id,),
        )
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
    print("Legal corpus registered; no documents, chunks or vectors copied or changed")


if __name__ == "__main__":
    main()
