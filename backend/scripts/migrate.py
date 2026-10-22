"""Explicit schema migration. Default is a confirmed read-only plan."""

import argparse
import os
import sqlite3
from pathlib import Path

from dotenv import dotenv_values

from backend.app.db.connection import connect, migrate_db
from backend.inventory.sql import Reader, identifier, open_reader


def backup(reader, path):
    # New private file; preserve all table data, including encrypted control-plane credentials.
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    with sqlite3.connect(path) as target:
        for table in reader.query(
            "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ):
            target.execute(table["sql"])
            columns = reader.query(f"PRAGMA table_info({identifier(table['name'])})")
            names = [column["name"] for column in columns]
            rows = reader.query(f"SELECT * FROM {identifier(table['name'])}")
            if rows:
                target.executemany(
                    f"INSERT INTO {identifier(table['name'])} VALUES({','.join('?' for _ in names)})",
                    [tuple(row[name] for name in names) for row in rows],
                )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path("backend/.env"))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", type=Path)
    args = parser.parse_args(argv)
    env = dict(os.environ) | {
        k: v for k, v in dotenv_values(args.env_file).items() if v is not None
    }
    url = env.get("TURSO_DATABASE_URL") or env.get("TURSO_CONNECTION_URL", "")
    token = env.get("TURSO_AUTH_TOKEN", "")
    if args.apply and not args.backup:
        parser.error(
            "--apply requires a new --backup path; stop application writers first"
        )
    if not args.apply:
        with open_reader(url, token) as reader:
            tables = reader.schema()
        print(
            "Read-only migration plan: initialize legacy schema"
            if "projects" not in tables
            else "Read-only migration plan: preserve legacy rows; ensure document_sources, index_generations, canonical_chunks"
        )
        return
    conn = connect(url, token)
    try:
        conn.execute("BEGIN IMMEDIATE")
        reader = Reader(conn)
        tables = reader.schema()
        backup(reader, args.backup)
        if "projects" not in tables:
            for statement in (
                (Path(__file__).parents[1] / "app/db/schema.sql").read_text().split(";")
            ):
                if statement.strip():
                    conn.execute(statement)
        migrate_db(conn)
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
    print("Migration complete; backup retained; no ingestion or retrieval cutover")


if __name__ == "__main__":
    main()
