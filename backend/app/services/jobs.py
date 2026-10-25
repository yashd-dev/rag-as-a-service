"""Durable private ingestion. One fenced writer per project, no request threads."""

import hashlib
import os
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path

from neo4j import GraphDatabase, Query

from backend.app.db.connection import db
from backend.app.db.repository import now_ms, rows_to_dicts
from backend.app.services.rag import fingerprint

FORMATS = {".pdf", ".txt", ".md", ".csv", ".json"}
LEASE_MS = 180_000
MAX_ATTEMPTS = 3


class LeaseLost(RuntimeError):
    pass


class Jobs:
    def __init__(self, config):
        self.config = config
        self.url, self.token = config["TURSO_DATABASE_URL"], config["TURSO_AUTH_TOKEN"]

    def upload(self, project, user_id, file, filename):
        root = Path(self.config["UPLOAD_DIR"]).resolve()
        root.mkdir(parents=True, exist_ok=True)
        maximum = int(self.config["MAX_UPLOAD_MB"]) * 1024 * 1024
        digest, size = hashlib.sha256(), 0
        with tempfile.NamedTemporaryFile(dir=root, delete=False) as temporary:
            temporary_path = Path(temporary.name)
            try:
                while block := file.stream.read(1024 * 1024):
                    size += len(block)
                    if size > maximum:
                        raise ValueError("file_too_large")
                    digest.update(block)
                    temporary.write(block)
                if not size:
                    raise ValueError("empty_file")
                temporary.flush()
                os.fsync(temporary.fileno())
            except BaseException:
                temporary_path.unlink(missing_ok=True)
                raise
        org, pid, byte_hash = project["organization_id"], project["id"], digest.hexdigest()
        document_id = "doc_" + fingerprint([org, pid, "upload", filename, byte_hash])
        path = root / "private" / fingerprint([org, pid]) / document_id / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            # The database transaction also serializes duplicate intake/deletion.
            with db(self.url, self.token) as conn:
                conn.execute("BEGIN IMMEDIATE")
                self.private_project(conn, org, pid)
                exists = conn.execute("SELECT 1 FROM ingestion_jobs WHERE document_id=?", (document_id,)).fetchone()
                if not exists:
                    # shortcut: an unacknowledged file can survive a DB failure; add age-based orphan cleanup when needed.
                    os.replace(temporary_path, path)
                    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
                    try:
                        os.fsync(descriptor)
                    finally:
                        os.close(descriptor)
                    timestamp = now_ms()
                    conn.execute(
                        "INSERT INTO documents(id,project_id,organization_id,uploaded_by_user_id,file_name,status,created_at,updated_at) VALUES(?,?,?,?,?,'pending',?,?) ON CONFLICT(id) DO NOTHING",
                        (document_id, pid, org, user_id, filename, timestamp, timestamp),
                    )
                    conn.execute(
                        "INSERT INTO ingestion_jobs(document_id,project_id,organization_id,file_path,file_hash,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                        (document_id, pid, org, str(path), byte_hash, timestamp, timestamp),
                    )
            return self.get(document_id, org)
        finally:
            temporary_path.unlink(missing_ok=True)

    @staticmethod
    def private_project(conn, org, pid):
        if not conn.execute(
            "SELECT 1 FROM projects p WHERE p.id=? AND p.organization_id=? AND NOT EXISTS (SELECT 1 FROM shared_corpora WHERE project_id=p.id) AND NOT EXISTS (SELECT 1 FROM project_corpus_references WHERE project_id=p.id)",
            (pid, org),
        ).fetchone():
            raise LeaseLost("private_project_unavailable")

    def get(self, document_id, org):
        with db(self.url, self.token) as conn:
            rows = rows_to_dicts(conn.execute("SELECT * FROM ingestion_jobs WHERE document_id=? AND organization_id=?", (document_id, org)))
        return self.safe(rows[0]) if rows else None

    @staticmethod
    def safe(row):
        return {key: value for key, value in row.items() if key not in {"file_path", "file_hash", "lease_token"}}

    def list(self, project):
        with db(self.url, self.token) as conn:
            rows = rows_to_dicts(conn.execute("SELECT * FROM ingestion_jobs WHERE project_id=? AND organization_id=? ORDER BY created_at", (project["id"], project["organization_id"])))
        return [self.safe(row) for row in rows]

    def claim(self):
        timestamp, token = now_ms(), uuid.uuid4().hex
        with db(self.url, self.token) as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT j.project_id,j.organization_id FROM ingestion_jobs j LEFT JOIN ingestion_project_leases l ON l.project_id=j.project_id WHERE j.state IN ('queued','active') AND j.next_attempt_at<=? AND (l.project_id IS NULL OR l.expires_at<=?) ORDER BY j.created_at LIMIT 1",
                (timestamp, timestamp),
            ).fetchone()
            if not row:
                return None
            pid, org = row
            self.private_project(conn, org, pid)
            conn.execute("INSERT INTO ingestion_project_leases VALUES(?,?,?) ON CONFLICT(project_id) DO UPDATE SET token=excluded.token,expires_at=excluded.expires_at", (pid, token, timestamp + LEASE_MS))
            conn.execute("UPDATE ingestion_jobs SET state='failed',stage='failed',error_code='attempts_exhausted',updated_at=? WHERE project_id=? AND state IN ('queued','active') AND attempts>=?", (timestamp, pid, MAX_ATTEMPTS))
            conn.execute("UPDATE ingestion_jobs SET state='active',lease_token=?,attempts=attempts+1,error_code=NULL,updated_at=? WHERE project_id=? AND state IN ('queued','active') AND attempts<? AND next_attempt_at<=?", (token, timestamp, pid, MAX_ATTEMPTS, timestamp))
            jobs = rows_to_dicts(conn.execute("SELECT * FROM ingestion_jobs WHERE project_id=? AND lease_token=? AND state='active'", (pid, token)))
        return {"project_id": pid, "organization_id": org, "token": token, "jobs": jobs}

    def validate(self, conn, claim):
        self.private_project(conn, claim["organization_id"], claim["project_id"])
        if not conn.execute("SELECT 1 FROM ingestion_project_leases WHERE project_id=? AND token=? AND expires_at>?", (claim["project_id"], claim["token"], now_ms())).fetchone():
            raise LeaseLost("ingestion_lease_lost")

    @contextmanager
    def fence(self, claim):
        with db(self.url, self.token) as conn:
            conn.execute("BEGIN IMMEDIATE")
            self.validate(conn, claim)
            yield conn

    def renew(self, claim):
        with self.fence(claim) as conn:
            conn.execute("UPDATE ingestion_project_leases SET expires_at=? WHERE project_id=?", (now_ms() + LEASE_MS, claim["project_id"]))

    def update(self, claim, document_id, **values):
        allowed = {"stage", "chunk_count", "vector_count", "state", "error_code", "next_attempt_at"}
        if not set(values) <= allowed:
            raise ValueError("invalid_job_update")
        with self.fence(claim) as conn:
            conn.execute("UPDATE ingestion_jobs SET " + ",".join(key + "=?" for key in values) + ",updated_at=? WHERE document_id=? AND lease_token=?", (*values.values(), now_ms(), document_id, claim["token"]))

    def release(self, claim):
        with db(self.url, self.token) as conn:
            conn.execute("UPDATE ingestion_project_leases SET expires_at=0 WHERE project_id=? AND token=?", (claim["project_id"], claim["token"]))

    def retry(self, project, document_id):
        with db(self.url, self.token) as conn:
            conn.execute("BEGIN IMMEDIATE")
            self.private_project(conn, project["organization_id"], project["id"])
            return conn.execute("UPDATE ingestion_jobs SET state='queued',stage='queued',attempts=0,next_attempt_at=0,error_code=NULL,updated_at=? WHERE document_id=? AND project_id=? AND organization_id=? AND state='failed'", (now_ms(), document_id, project["id"], project["organization_id"])).rowcount > 0

    def clean_files(self):
        root = Path(self.config["UPLOAD_DIR"]).resolve()
        with db(self.url, self.token) as conn:
            rows = conn.execute("SELECT path FROM upload_cleanup LIMIT 100").fetchall()
        for (value,) in rows:
            path = Path(value).resolve()
            try:
                if not path.is_relative_to(root) or path == root:
                    raise ValueError("invalid_cleanup_path")
                path.unlink(missing_ok=True)
                with db(self.url, self.token) as conn:
                    conn.execute("DELETE FROM upload_cleanup WHERE path=?", (value,))
            except (OSError, ValueError):
                with db(self.url, self.token) as conn:
                    conn.execute("UPDATE upload_cleanup SET error_code='file_cleanup_failed' WHERE path=?", (value,))

    def remove(self, project, document_id=None):
        org, pid = project["organization_id"], project["id"]
        with db(self.url, self.token) as conn:
            conn.execute("BEGIN IMMEDIATE")
            self.private_project(conn, org, pid)
            documents = rows_to_dicts(conn.execute(
                "SELECT * FROM documents WHERE project_id=? AND organization_id=?" + (" AND id=?" if document_id else ""),
                (pid, org, document_id) if document_id else (pid, org),
            ))
            if document_id and not documents:
                return False
            # Holding the same metadata fence excludes every worker Neo4j write.
            with GraphDatabase.driver(self.config["NEO4J_URI"], auth=(self.config["NEO4J_USERNAME"], self.config["NEO4J_PASSWORD"])) as driver, driver.session(default_access_mode="WRITE") as session:
                session.run(Query("MATCH (n) WHERE n.organization_id=$org AND n.project_id=$project DETACH DELETE n", timeout=30), org=org, project=pid).consume()
            conn.execute("UPDATE ingestion_project_leases SET token=?,expires_at=0 WHERE project_id=?", (uuid.uuid4().hex, pid))
            for document in documents:
                paths = conn.execute("SELECT file_path FROM ingestion_jobs WHERE document_id=? AND file_path IS NOT NULL", (document["id"],)).fetchall()
                legacy = (Path(self.config["UPLOAD_DIR"]).resolve() / org / pid / document["id"] / document["file_name"]).resolve()
                if legacy.exists() and legacy.is_relative_to(Path(self.config["UPLOAD_DIR"]).resolve()):
                    paths.append((str(legacy),))
                for (path,) in paths:
                    conn.execute("INSERT INTO upload_cleanup(path,organization_id,project_id,created_at) VALUES(?,?,?,?) ON CONFLICT(path) DO NOTHING", (path, org, pid, now_ms()))
            if document_id:
                conn.execute("DELETE FROM documents WHERE id=? AND project_id=? AND organization_id=?", (document_id, pid, org))
                # Remaining canonical text is retained; its new corpus manifest needs publication.
                for (remaining,) in conn.execute("SELECT id FROM documents WHERE project_id=? AND organization_id=?", (pid, org)).fetchall():
                    conn.execute("INSERT INTO ingestion_jobs(document_id,project_id,organization_id,created_at,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(document_id) DO UPDATE SET state='queued',stage='queued',attempts=0,next_attempt_at=0,lease_token=NULL,vector_count=0,error_code=NULL,updated_at=excluded.updated_at", (remaining, pid, org, now_ms(), now_ms()))
            else:
                conn.execute("DELETE FROM query_runs WHERE project_id=? AND organization_id=?", (pid, org))
                conn.execute("DELETE FROM projects WHERE id=? AND organization_id=?", (pid, org))
        return True
