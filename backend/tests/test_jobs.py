import io
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from werkzeug.datastructures import FileStorage

from backend.app import create_app
from backend.app.db.indexing import IdentityConflict
from backend.app.services import ingestion_worker
from backend.app.services.jobs import Jobs, LeaseLost
from backend.tests.test_index_state import query


@pytest.fixture
def queued(store, tmp_path):
    index, path, project = store
    config = {
        "TESTING": True, "TURSO_DATABASE_URL": index.url,
        "TURSO_AUTH_TOKEN": index.token, "UPLOAD_DIR": tmp_path / "uploads",
        "MAX_UPLOAD_MB": 1, "BACKEND_INTERNAL_SECRET": "test-secret",
        "NEO4J_URI": "bolt://fixture", "NEO4J_USERNAME": "fixture", "NEO4J_PASSWORD": "fixture",
    }
    queue = Jobs(config)
    file = FileStorage(io.BytesIO(b"Private source evidence."), filename="one.txt")
    job = queue.upload(project, "u", file, "one.txt")
    return queue, config, path, project, job, index


def test_upload_is_atomic_durable_deduplicated_and_status_is_scoped(queued):
    queue, config, path, project, job, _ = queued
    same = queue.upload(project, "u", FileStorage(io.BytesIO(b"Private source evidence.")), "one.txt")
    assert same["document_id"] == job["document_id"]
    assert query(path, "SELECT count(*) FROM documents") == [(1,)]
    assert query(path, "SELECT count(*) FROM ingestion_jobs") == [(1,)]
    assert query(path, "SELECT count(*) FROM canonical_chunks") == [(0,)]
    original = query(path, "SELECT file_path FROM ingestion_jobs")[0][0]
    assert Path(original).read_bytes() == b"Private source evidence."
    assert "file_path" not in job and "file_hash" not in job and "lease_token" not in job
    app = create_app(type("Config", (), config))
    headers = {"X-Internal-Secret": "test-secret", "X-User-Id": "u", "X-Organization-Id": "o"}
    client = app.test_client()
    assert client.get("/api/projects/p/jobs", headers=headers).json["items"][0]["state"] == "queued"
    assert client.get("/api/projects/p/jobs", headers=headers | {"X-Organization-Id": "foreign"}).status_code == 404
    assert client.post("/api/projects/p/documents/upload", headers=headers, data={"file": (io.BytesIO(b"bad"), "bad.exe")}).status_code == 415
    assert client.post("/api/projects/p/documents/upload", headers=headers, data={"file": (io.BytesIO(b""), "empty.txt")}).status_code == 400
    assert query(path, "SELECT count(*) FROM ingestion_jobs") == [(1,)]


def test_competing_workers_crash_takeover_and_expired_fencing(queued):
    queue, config, path, project, job, index = queued
    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(lambda _: Jobs(config).claim(), range(2)))
    old = next(claim for claim in claims if claim)
    assert sum(claim is not None for claim in claims) == 1
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE ingestion_project_leases SET expires_at=0")
    current = queue.claim()
    assert current["token"] != old["token"]
    assert current["jobs"][0]["attempts"] == 2
    with pytest.raises(LeaseLost), queue.fence(old):
        pytest.fail("Old worker obtained a fence")
    with pytest.raises(LeaseLost):
        index.stage(project, "upload", job["document_id"], "Late old worker", document_id=job["document_id"], authorize=lambda conn: queue.validate(conn, old))
    assert query(path, "SELECT count(*) FROM canonical_chunks") == [(0,)]
    queue.renew(current)
    with queue.fence(current):
        pass


def test_worker_stages_embeds_publishes_and_retries_without_duplicate_text(queued, monkeypatch):
    queue, config, path, _, job, _ = queued
    state = {"fail": True, "published": False}

    class Provider:
        def resolve(self):
            return {"provider": "test-only", "dimensions": 768}

    class Vectors:
        def __init__(self, config, snapshot, provenance, *, write_guard):
            self.snapshot, self.guard = snapshot, write_guard

        def build(self, provider, batch_size, progress):
            if state["fail"]:
                raise RuntimeError("private-provider-details")
            with self.guard():
                progress_ids = {row["id"] for row in self.snapshot["rows"]}
            progress(progress_ids)

        def publish(self):
            with self.guard():
                state["published"] = True

        def close(self):
            pass

    monkeypatch.setattr(ingestion_worker, "embedding_provider_for_project", lambda *args: Provider())
    monkeypatch.setattr(ingestion_worker, "Neo4jVectorStore", Vectors)
    assert ingestion_worker.run_once(config)
    failed = queue.get(job["document_id"], "o")
    assert failed["state"] == "queued" and failed["error_code"] == "indexing_unavailable"
    assert query(path, "SELECT count(*) FROM canonical_chunks") == [(1,)]
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE ingestion_jobs SET next_attempt_at=0")
    state["fail"] = False
    assert ingestion_worker.run_once(config)
    completed = queue.get(job["document_id"], "o")
    assert completed["state"] == "completed" and state["published"]
    assert completed["vector_count"] == completed["chunk_count"] == 1
    assert query(path, "SELECT count(*) FROM canonical_chunks") == [(1,)]
    assert query(path, "SELECT count(*) FROM index_generations") == [(1,)]
    assert not ingestion_worker.run_once(config)


def test_delete_fences_worker_and_durably_cleans_original(queued, monkeypatch):
    queue, _, path, project, job, index = queued
    claim = queue.claim()
    original = query(path, "SELECT file_path FROM ingestion_jobs")[0][0]

    class Result:
        def consume(self):
            pass

    class Store:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def session(self, **kwargs):
            return self

        def run(self, query, **params):
            assert params == {"org": "o", "project": "p"}
            return Result()

    monkeypatch.setattr("backend.app.services.jobs.GraphDatabase.driver", lambda *args, **kwargs: Store())
    assert queue.remove(project, job["document_id"])
    with pytest.raises(LeaseLost), queue.fence(claim):
        pytest.fail("Deleted document's worker obtained a fence")
    with pytest.raises(IdentityConflict):
        index.stage(project, "upload", job["document_id"], "Late worker", document_id=job["document_id"])
    assert query(path, "SELECT count(*) FROM documents") == [(0,)]
    assert query(path, "SELECT count(*) FROM upload_cleanup") == [(1,)]
    queue.clean_files()
    assert not Path(original).exists()
    assert query(path, "SELECT count(*) FROM upload_cleanup") == [(0,)]
