"""Read-only SQL transport and schema discovery, independent of Flask startup."""

import hashlib
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class AccessBlocked(RuntimeError):
    """Safe, enumerated reason; never carries a driver's exception message."""

    def __init__(self, reason, error_type=None):
        super().__init__(reason)
        self.reason = reason
        self.error_type = error_type


def blocked(exc):
    if isinstance(exc, AccessBlocked):
        return {"state": "blocked", "reason": exc.reason, "error_type": exc.error_type}
    return {"state": "blocked", "error_type": type(exc).__name__}


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
        if re.search(
            r"\b(load_extension|writefile|readfile)\s*\(", statement, re.IGNORECASE
        ):
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
    if not url:
        raise AccessBlocked("missing_database_url")
    if url.startswith("file:"):
        # Resolve only existing files; no fallback or accidental empty creation.
        path = Path(url[5:]).resolve(strict=True)
        connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    elif url.startswith(("libsql://", "https://")):
        if not token:
            raise AccessBlocked("missing_auth_token")
        from backend.inventory.hrana import Connection

        try:
            connection = Connection(url, token)
        except Exception as exc:  # noqa: BLE001 - redact connection errors
            raise AccessBlocked("connection_failed", type(exc).__name__) from None
    else:
        raise AccessBlocked("unsupported_database_url_scheme")
    try:
        if isinstance(connection, sqlite3.Connection):
            connection.execute("PRAGMA query_only = ON")
            if connection.execute("PRAGMA query_only").fetchone()[0] != 1:
                raise AccessBlocked("query_only_not_confirmed")
        yield Reader(connection)
    finally:
        connection.close()
