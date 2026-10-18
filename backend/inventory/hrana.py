"""Read-only Hrana HTTP adapter: server describes each statement before execution.

Protocol: https://github.com/tursodatabase/libsql/blob/main/docs/HRANA_3_SPEC.md
No raw SQL execution is exposed without the server's is_readonly confirmation.
"""

from base64 import b64decode
from urllib.parse import urlsplit

import httpx


class ReadOnlyError(RuntimeError):
    """Intentionally secret-free transport error."""


def encode(value):
    if value is None:
        return {"type": "null"}
    if isinstance(value, int):
        return {"type": "integer", "value": str(value)}
    if isinstance(value, str):
        return {"type": "text", "value": value}
    raise TypeError("Unsupported diagnostic SQL argument")


def decode(value):
    kind = value["type"]
    if kind == "null":
        return None
    if kind == "integer":
        return int(value["value"])
    if kind == "float":
        return float(value["value"])
    if kind == "text":
        return value["value"]
    if kind == "blob":
        return b64decode(value["base64"], validate=True)
    raise ReadOnlyError("Unexpected Hrana value type")


class Cursor:
    def __init__(self, result):
        self.description = [(column["name"],) for column in result["cols"]]
        self.rows = [tuple(decode(value) for value in row) for row in result["rows"]]

    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self, url, token):
        self.base = url.replace("libsql://", "https://", 1).rstrip("/")
        parsed = urlsplit(self.base)
        if parsed.scheme != "https" or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ReadOnlyError("Expected credential-free HTTPS database URL")
        self.client = httpx.Client(
            headers={"Authorization": f"Bearer {token}"}, timeout=60, follow_redirects=False,
        )

    def pipeline(self, base, baton, requests):
        response = self.client.post(base + "/v2/pipeline", json={"baton": baton, "requests": requests})
        response.raise_for_status()
        payload = response.json()
        target = (payload.get("base_url") or base).rstrip("/")
        # Never forward a bearer token or baton to a different origin.
        if urlsplit(target).netloc != urlsplit(self.base).netloc or urlsplit(target).scheme != "https":
            raise ReadOnlyError("Cross-origin Hrana routing refused")
        return payload, target

    def execute(self, statement, parameters=()):
        payload, base = self.pipeline(self.base, None, [{"type": "describe", "sql": statement}])
        baton = payload.get("baton")
        try:
            description = payload["results"][0]
            if description.get("type") != "ok":
                raise ReadOnlyError("Server could not describe diagnostic statement")
            if description["response"]["result"].get("is_readonly") is not True:
                raise ReadOnlyError("Server did not confirm statement is read-only")
            result, _ = self.pipeline(base, baton, [
                {"type": "execute", "stmt": {"sql": statement,
                                            "args": [encode(value) for value in parameters]}},
                {"type": "close"},
            ])
            baton = None  # close was included, even when the execute request fails
            execution = result["results"][0]
            if execution.get("type") != "ok":
                raise ReadOnlyError("Read-only statement execution failed")
            return Cursor(execution["response"]["result"])
        finally:
            if baton:
                self.pipeline(base, baton, [{"type": "close"}])

    def close(self):
        self.client.close()
