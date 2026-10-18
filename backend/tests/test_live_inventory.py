import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

import pytest

from backend.inventory import live
from backend.inventory.sql import open_reader


def test_source_full_scan_fingerprints_exclusions_and_no_text_emission(tmp_path):
    path = tmp_path / "ocr.db"
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE pdfs (path TEXT PRIMARY KEY, url TEXT, ocr_text TEXT, ocr_status TEXT,
                updated_at TEXT, etag TEXT, last_modified TEXT, page_count INTEGER);
            INSERT INTO pdfs VALUES
                ('one', 'url', 'private real text', 'done', '2026-10-18', 'etag', 'date', NULL),
                ('two', 'url', '   ', 'done', '2026-10-18', 'etag', 'date', NULL),
                ('three', 'url', NULL, 'failed', '2026-10-18', 'etag', 'date', NULL),
                ('four', 'url', NULL, 'pending', '2026-10-18', 'etag', 'date', NULL);
        """)
    report, records, probe = live.source_inventory({"OCR_TURSO_DB": "file:" + str(path)})
    assert report["watermarks_match"] is True
    assert report["counts_reconciled"] is True
    assert report["classification"]["requires_initial_chunking_and_embedding"] == 1
    assert report["classification"]["requires_text_provenance_repair"] == 3
    assert report["counts"]["distinct_ids"] == 4
    assert report["metadata_coverage"]["with_page_count"] == 0
    assert len(report["manifest"]) == 4
    assert probe == "private real text"
    assert records["one"]["eligible_text"] is True
    assert "private real text" not in json.dumps(report)
    assert "private real text" not in json.dumps(records)


def test_app_empty_vectors_and_historical_source_flags_do_not_imply_readiness(tmp_path, monkeypatch):
    path = tmp_path / "app.db"
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE projects (id TEXT, organization_id TEXT, embedding_provider TEXT, embedding_model TEXT);
            INSERT INTO projects VALUES ('p', 'o', 'label', 'not-vector-provenance');
            CREATE TABLE documents (id TEXT, organization_id TEXT, project_id TEXT, file_name TEXT, status TEXT, updated_at INTEGER);
            INSERT INTO documents VALUES ('d', 'o', 'p', 'one', 'ready', 1), ('upload', 'o', 'p', 'upload', 'pending', 1);
            CREATE TABLE chunk_embeddings (id TEXT, organization_id TEXT, project_id TEXT, document_id TEXT, content TEXT, embedding TEXT);
            CREATE TABLE data_sources (id TEXT, organization_id TEXT, source_type TEXT, prefix TEXT, endpoint_url TEXT, updated_at INTEGER);
            INSERT INTO data_sources VALUES ('s', 'o', 'turso_ocr', '{"project_id":"deleted", "ingestion_status":"running"}', 'private-url', 1);
        """)

    @contextmanager
    def reader(*args):
        with open_reader(*args) as connection:
            connection.connection.create_function("vector_extract", 1, lambda value: value)
            yield connection

    monkeypatch.setattr(live, "open_reader", reader)
    report = live.app_inventory({"TURSO_DATABASE_URL": "file:" + str(path)}, {
        "one": {"content_sha256": "source-hash", "eligible_text": True},
    })
    assert report["retrieval_coverage"]["documents_with_stored_vectors"] == 0
    assert report["retrieval_coverage"]["expected_chunk_count"] is None
    assert report["projects"][0]["vectors"]["stale_count"] == 0
    assert report["projects"][0]["blockers"] == []
    assert report["reconciliation"]["exact_source_path_matches"] == 1
    assert report["reconciliation"]["unmatched_application_documents"] == 1
    assert report["source_configuration_integrity"]["mapped_project_missing_or_foreign"] == 1
    assert report["source_configuration_integrity"]["ingestion_statuses"] == {"running": 1}
    assert "private-url" not in json.dumps(report)


@pytest.mark.parametrize(("changed_digest", "different_dimensions", "expected"), [
    (False, False, "measured"), (True, False, "blocked"), (False, True, "blocked"),
])
def test_model_checks_served_digest_and_actual_source_query_widths(monkeypatch, changed_digest, different_dimensions, expected):
    import httpx

    tag_reads = []
    requests = []

    def respond(request):
        requests.append(request)
        if request.url.path == "/api/tags":
            tag_reads.append(1)
            digest = "changed" if changed_digest and len(tag_reads) > 1 else "original"
            return httpx.Response(200, json={"models": [{"name": "embeddinggemma:latest", "digest": digest}]})
        if request.url.path == "/api/show":
            return httpx.Response(200, json={"model_info": {"gemma3.embedding_length": 3}})
        assert request.url.path == "/api/embed"
        assert json.loads(request.content)["input"][1] == "actual private source excerpt"
        return httpx.Response(200, json={"embeddings": [[1, 2, 3], [1, 2] if different_dimensions else [1, 2, 3]]})

    client_type = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: client_type(
        **kwargs, transport=httpx.MockTransport(respond)))
    report = live.model_inventory({"OLLAMA_BASE_URL": "http://model"}, "actual private source excerpt")
    assert report["state"] == expected
    assert report["persisted_vectors"] == 0
    assert report["actual_source_excerpt_probed"] is True
    assert "actual private source excerpt" not in json.dumps(report)
    assert len(requests) == 4


@pytest.mark.parametrize("nodes", [0, 10])
def test_graph_empty_denominators_are_not_readiness_and_nonempty_needs_mapping(monkeypatch, nodes):
    import neo4j

    queries = []

    class ReadSession:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute_read(self, callback):
            return callback(self)

        def run(self, query):
            queries.append(query)
            if query == "MATCH (n) RETURN count(n) AS count":
                return [{"count": nodes}]
            if query == "MATCH ()-[r]->() RETURN count(r) AS count":
                return [{"count": 0}]
            return []

        def session(self, **kwargs):
            assert kwargs["default_access_mode"] == neo4j.READ_ACCESS
            return self

    monkeypatch.setattr(neo4j.GraphDatabase, "driver", lambda *args, **kwargs: ReadSession())
    report = live.graph_inventory({"NEO4J_URI": "bolt://test", "NEO4J_USERNAME": "u", "NEO4J_PASSWORD": "secret"})
    assert len(queries) == 9
    if nodes == 0:
        assert report["coverage"]["state"] == "verified_empty_database_not_ready"
        assert report["coverage"]["assertions_with_valid_chunk_document_evidence"] == {"valid": 0, "total": 0}
    else:
        assert report["coverage"]["state"] == "blocked"


def test_service_failure_keeps_other_independent_measurements_and_gate_closed(monkeypatch):
    def failing_source(env):
        raise RuntimeError("secret token must never be reported")

    monkeypatch.setattr(live, "source_inventory", failing_source)
    monkeypatch.setattr(live, "app_inventory", lambda env, records: {"state": "measured"})
    monkeypatch.setattr(live, "graph_inventory", lambda env: {"state": "measured"})
    monkeypatch.setattr(live, "model_inventory", lambda env, text: {"state": "measured"})
    report = live.inventory({})
    assert report["measurement_status"] == "incomplete"
    assert report["application"]["state"] == "measured"
    assert report["gate"] == "CLOSED_PENDING_USER_REVIEW"
    assert "secret token" not in json.dumps(report)


def test_versioned_live_evidence_is_coherent_and_does_not_claim_index_readiness():
    path = Path(__file__).parents[1] / "inventory/reports/2026-10-18-live.json"
    report = json.loads(path.read_text())
    source = report["source"]
    app = report["application"]
    assert report["measurement_status"] == "complete"
    assert report["review"]["decision"] == "pending"
    assert report["gate"] == "CLOSED_PENDING_USER_REVIEW"
    assert source["counts"]["total"] == len(source["manifest"])
    assert source["manifest_sha256"] == live.digest(json.dumps(source["manifest"], sort_keys=True))
    assert sum(row["eligible_text"] for row in source["manifest"]) == source["classification"]["requires_initial_chunking_and_embedding"]
    assert source["watermark_before"] == source["watermark_after"]
    assert app["table_counts"]["documents"] == len(app["documents"])
    assert sum(p["tables"]["documents"]["count"] for p in app["projects"]) == len(app["documents"])
    assert app["table_counts"]["chunk_embeddings"] == sum(p["tables"]["chunk_embeddings"]["count"] for p in app["projects"])
    assert app["global_vector_integrity"]["total"] == 0
    assert app["retrieval_coverage"]["documents_with_stored_vectors"] == 0
    assert report["neo4j"]["coverage"]["state"] == "verified_empty_database_not_ready"
    assert all(probe["dimension"] == 768 for probe in report["model"]["probes"])
    assert report["model"]["digest_before"] == report["model"]["digest_after"]


@pytest.mark.parametrize("defect", [None, "orphan_vectors", "blockers", "unknown_staleness",
                                   "unknown_generation", "unclassified", "short_scan", "source_changed"])
def test_completion_rejects_missing_required_measurements(defect):
    path = Path(__file__).parents[1] / "inventory/reports/2026-10-18-live.json"
    report = json.loads(path.read_text())
    report["source"]["counts_reconciled"] = True
    project = report["application"]["projects"][0]
    if defect == "orphan_vectors":
        report["application"]["table_counts"]["chunk_embeddings"] = 3
        report["application"]["global_vector_integrity"]["total"] = 3
    elif defect == "blockers":
        project["blockers"] = ["unverified vector provenance"]
    elif defect == "unknown_staleness":
        project["vectors"]["stale_count"] = None
    elif defect == "unknown_generation":
        project["vectors"]["generation_distribution"] = None
    elif defect == "unclassified":
        project["vectors"]["classification"] = {"unknown_blocked": 3}
    elif defect == "short_scan":
        project["tables"]["chunk_embeddings"]["count"] = 3
    elif defect == "source_changed":
        report["source"]["counts_reconciled"] = False
    assert bool(live.measurement_issues(report)) is (defect is not None)


def test_source_change_during_initial_counts_is_detected(monkeypatch):
    events = []

    class Reader:
        def __init__(self):
            self.queries = []

        def query(self, sql):
            if "max(updated_at)" in sql:
                events.append("watermark")
                return [{"records": 2 if len(events) == 1 else 1, "latest_updated_at": "date"}]
            if "count(url)" in sql:
                return [{"records": 1}]
            return [{"ocr_status": "done", "records": 1}]

    @contextmanager
    def reader(*args):
        yield Reader()

    def initial_counts(*args):
        events.append("counts")
        return {"state": "measured", "counts": {"total": 2, "distinct_ids": 2, "nonempty_text": 2},
                "eligible_ocr_counts": {"rows": 2, "nonempty_text": 2}}

    monkeypatch.setattr(live, "open_reader", reader)
    monkeypatch.setattr(live, "source_report", initial_counts)
    monkeypatch.setattr(live, "scan", lambda *args, **kwargs: iter([
        {"path": "one", "ocr_text": "real text", "ocr_status": "done", "updated_at": "date"},
    ]))
    report, _, _ = live.source_inventory({"OCR_TURSO_DB": "file:fixture"})
    assert events[:2] == ["watermark", "counts"]
    assert report["watermarks_match"] is False
    assert report["counts_reconciled"] is False


def test_source_counts_classification_and_selection_share_whitespace_policy(tmp_path):
    from backend.inventory.report import source_report

    path = tmp_path / "whitespace.db"
    rows = [("a", "real text"), ("b", "\n\t"), ("c", "\u2003\u00a0"),
            ("d", "\x00actual text"), ("e", None), ("f", "  ")]
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE pdfs (path TEXT PRIMARY KEY, ocr_text TEXT, ocr_status TEXT, "
                           "url TEXT, updated_at TEXT, etag TEXT, last_modified TEXT, page_count INTEGER)")
        connection.executemany("INSERT INTO pdfs VALUES (?, ?, 'done', 'url', 'date', 'etag', 'date', NULL)", rows)
    with open_reader("file:" + str(path)) as reader:
        scoped = source_report(reader, live.SOURCE_MAPPING)
        full, _, _ = live.source_inventory({"OCR_TURSO_DB": "file:" + str(path)})
        candidates = reader.query(full["selector"]["candidate_sql"])
    selected = [r["path"] for r in candidates if r["path"] and live.has_text(r["ocr_text"])]
    assert selected == ["a", "d"]
    assert scoped["eligible_ocr_counts"]["nonempty_text"] == len(selected)
    assert full["classification"]["requires_initial_chunking_and_embedding"] == len(selected)
    assert full["selector"]["eligible_source_id_sha256"] == [live.digest(key) for key in selected]
    assert full["counts_reconciled"] is True
    assert full["coverage_by_status"][0]["nonempty_text"] == len(selected)
