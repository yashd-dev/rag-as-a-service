"""Read-only SQL transport and schema discovery, independent of Flask startup."""

import hashlib
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path


def identifier(value):
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ValueError("Invalid SQL identifier")
    return '"' + value.replace('"', '""') + '"'


def connection_id(url):
    # Even hostnames/paths may contain private identifiers or embedded credentials.
    return "sha256:" + hashlib.sha256(url.encode()).hexdigest()[:16]


class Reader:
    def __init__(self, connection):
        self.connection = connection
        self.queries = []

    def query(self, statement, parameters=()):
        # Only internally generated SELECT and table_info statements. No arbitrary
        # SQL CLI input, scripts, CALLs, CTEs, extension loading or write pragmas.
        if not re.match(r"^(SELECT\s|PRAGMA table_info\()", statement):
            raise ValueError("Diagnostic SQL must be a read")
        if ";" in statement or "--" in statement or "/*" in statement:
            raise ValueError("Multiple statements/comments are prohibited")
        if re.search(r"\b(load_extension|writefile|readfile)\s*\(", statement, re.IGNORECASE):
            raise ValueError("Extension and filesystem functions are prohibited")
        self.queries.append(statement)
        cursor = self.connection.execute(statement, parameters)
        names = [column[0] for column in cursor.description]
        return [dict(zip(names, row)) for row in cursor.fetchall()]

    def schema(self):
        tables = self.query(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        )
        return {
            row["name"]: self.query(f"PRAGMA table_info({identifier(row['name'])})")
            for row in tables
        }


@contextmanager
def open_reader(url, token=""):
    if url.startswith("file:"):
        # Resolve only existing files; no fallback or accidental empty creation.
        path = Path(url[5:]).resolve(strict=True)
        connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    elif url.startswith(("libsql://", "https://")) and token:
        import libsql

        connection = libsql.connect(database=url, auth_token=token)
    else:
        raise ValueError("An explicit file: path or authenticated Turso URL is required")
    try:
        # Fail closed if a server/driver cannot enforce/confirm query_only.
        connection.execute("PRAGMA query_only = ON")
        if connection.execute("PRAGMA query_only").fetchone()[0] != 1:
            raise RuntimeError("Database did not confirm query_only")
        yield Reader(connection)
    finally:
        connection.close()
