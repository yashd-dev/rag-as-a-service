"""Revocable high-entropy platform keys and database-backed admission limits."""

import hashlib
import json
import secrets

from backend.app.db.connection import db
from backend.app.db.repository import new_id, now_ms, row_to_dict, rows_to_dicts
from backend.app.services.auth_context import AuthContext
from backend.app.services.corpus_access import CorpusAccess


class ApiError(RuntimeError):
    def __init__(self, code, status=400):
        super().__init__(code)
        self.code, self.status = code, status


class ApiKeys:
    def __init__(self, config):
        self.config = config
        self.url, self.token = config["TURSO_DATABASE_URL"], config["TURSO_AUTH_TOKEN"]

    def create(self, auth, payload):
        if not isinstance(payload, dict):
            raise ApiError("invalid_key_request")
        name, ids = payload.get("name"), payload.get("corpus_ids")
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
            raise ApiError("invalid_key_name")
        if not isinstance(ids, list) or not 1 <= len(ids) <= 20 or any(not isinstance(value, str) or not 1 <= len(value) <= 256 for value in ids) or len(set(ids)) != len(ids):
            raise ApiError("explicit_corpus_scope_required")
        for project_id in ids:
            CorpusAccess(self.config).resolve(auth, project_id)
        value, key_id = "rag_" + secrets.token_urlsafe(32), new_id("key")
        with db(self.url, self.token) as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("INSERT INTO platform_api_keys(id,organization_id,owner_user_id,name,prefix,secret_hash,created_at) VALUES(?,?,?,?,?,?,?)", (key_id, auth.organization_id, auth.user_id, name.strip(), value[:12], hashlib.sha256(value.encode()).hexdigest(), now_ms()))
            for project_id in ids:
                if not conn.execute("SELECT 1 FROM projects WHERE id=? AND organization_id=?", (project_id, auth.organization_id)).fetchone():
                    raise ApiError("corpus_not_found", 404)
                conn.execute("INSERT INTO platform_api_key_corpora VALUES(?,?)", (key_id, project_id))
        return {"id": key_id, "key": value, "corpus_ids": ids}

    def list(self, auth):
        with db(self.url, self.token) as conn:
            rows = rows_to_dicts(conn.execute("SELECT id,name,prefix,created_at,revoked_at FROM platform_api_keys WHERE organization_id=? AND owner_user_id=? ORDER BY created_at DESC", (auth.organization_id, auth.user_id)))
            for row in rows:
                row["corpus_ids"] = [item[0] for item in conn.execute("SELECT project_id FROM platform_api_key_corpora WHERE key_id=?", (row["id"],)).fetchall()]
                row["request_count"] = conn.execute("SELECT count(*) FROM platform_api_usage WHERE key_id=?", (row["id"],)).fetchone()[0]
        return rows

    def revoke(self, auth, key_id):
        with db(self.url, self.token) as conn:
            return conn.execute("UPDATE platform_api_keys SET revoked_at=? WHERE id=? AND organization_id=? AND owner_user_id=?", (now_ms(), key_id, auth.organization_id, auth.user_id)).rowcount > 0

    def authenticate(self, authorization):
        if not isinstance(authorization, str) or not authorization.startswith("Bearer rag_") or len(authorization) > 256:
            raise ApiError("invalid_api_key", 401)
        token = authorization.removeprefix("Bearer ")
        with db(self.url, self.token) as conn:
            row = row_to_dict(conn.execute("SELECT id,organization_id,owner_user_id FROM platform_api_keys WHERE secret_hash=? AND revoked_at IS NULL", (hashlib.sha256(token.encode()).hexdigest(),)))
        if row is None:
            raise ApiError("invalid_api_key", 401)
        return row, AuthContext(row["owner_user_id"], row["organization_id"], "api_key")

    def scope(self, key_id, corpus_id):
        if not isinstance(corpus_id, str) or not corpus_id:
            raise ApiError("corpus_id_required")
        with db(self.url, self.token) as conn:
            if not conn.execute("SELECT 1 FROM platform_api_key_corpora s JOIN platform_api_keys k ON k.id=s.key_id WHERE s.key_id=? AND s.project_id=? AND k.revoked_at IS NULL", (key_id, corpus_id)).fetchone():
                raise ApiError("corpus_scope_denied", 403)

    def begin(self, key, corpus_id, model):
        timestamp, request_id = now_ms(), new_id("api")
        with db(self.url, self.token) as conn:
            conn.execute("BEGIN IMMEDIATE")
            if not conn.execute("SELECT 1 FROM platform_api_keys WHERE id=? AND revoked_at IS NULL", (key["id"],)).fetchone():
                raise ApiError("invalid_api_key", 401)
            conn.execute("UPDATE platform_api_usage SET finished_at=?,status_code=504 WHERE finished_at IS NULL AND lease_until<=?", (timestamp, timestamp))
            for field, value, rate in (("key_id", key["id"], 20), ("organization_id", key["organization_id"], 60)):
                # Field names are fixed above, never supplied by callers.
                if conn.execute(f"SELECT count(*) FROM platform_api_usage WHERE {field}=? AND requested_at>?", (value, timestamp - 60_000)).fetchone()[0] >= rate:
                    raise ApiError("rate_limit_exceeded", 429)
            conn.execute("INSERT INTO platform_api_usage(id,key_id,organization_id,project_id,generation_config,requested_at,lease_until) VALUES(?,?,?,?,?,?,?)", (request_id, key["id"], key["organization_id"], corpus_id, model, timestamp, timestamp + 900_000))
        return request_id

    def finish(self, request_id, status, result=None):
        result = result or {}
        usage = result.get("generation", {}).get("usage")
        with db(self.url, self.token) as conn:
            conn.execute("UPDATE platform_api_usage SET finished_at=?,status_code=?,query_run_id=?,usage_json=? WHERE id=? AND finished_at IS NULL", (now_ms(), status, result.get("query_run_id"), json.dumps(usage) if usage else None, request_id))
