"""Restart-safe worker reusing canonical staging and the verified vector pipeline."""

import hashlib
import logging
import threading
from pathlib import Path

from backend.app.db.repository import ProjectRepository, now_ms
from backend.app.services.embedding_service import embedding_provider_for_project
from backend.app.services.evidence_graph import EvidenceGraph
from backend.app.services.graph_extraction import graph_extractor_for_project
from backend.app.services.ingestion_service import IngestionError, IngestionService
from backend.app.services.jobs import MAX_ATTEMPTS, Jobs, LeaseLost
from backend.app.services.neo4j_vectors import Neo4jVectorStore, canonical_snapshot


def run_once(config):
    queue = Jobs(config)
    queue.clean_files()
    claim = queue.claim()
    if claim is None:
        return False
    stopped = threading.Event()

    def heartbeat():
        while not stopped.wait(30):
            try:
                queue.renew(claim)
            except Exception:  # noqa: BLE001 - a renewal failure must stop heartbeats
                stopped.set()

    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    active = []

    def fail(job, code):
        queue.update(
            claim, job["document_id"],
            state="failed" if job["attempts"] >= MAX_ATTEMPTS else "queued",
            stage="failed", error_code=code,
            next_attempt_at=now_ms() + 10_000 * 2 ** (job["attempts"] - 1),
        )

    try:
        project = ProjectRepository(queue.url, queue.token).get(claim["project_id"], claim["organization_id"])
        ingestion = IngestionService(config)
        for job in claim["jobs"]:
            try:
                queue.update(claim, job["document_id"], stage="extraction")
                if job["file_path"]:
                    path = Path(job["file_path"]).resolve()
                    root = Path(config["UPLOAD_DIR"]).resolve()
                    if not path.is_relative_to(root):
                        raise ValueError("invalid_upload_path")
                    with path.open("rb") as original:
                        if hashlib.file_digest(original, "sha256").hexdigest() != job["file_hash"]:
                            raise ValueError("original_hash_mismatch")
                    if not ingestion.index.readiness(project, job["document_id"])["capabilities"]["text"]:
                        text, metadata = ingestion.extract_text(path)
                        if len(text.encode("utf-8")) > 20 * 1024 * 1024:
                            raise ValueError("extracted_text_too_large")
                        queue.update(claim, job["document_id"], stage="chunking")
                        document = ingestion.documents.get(job["document_id"], project["organization_id"])
                        ingestion.index.stage(
                            project, "upload", job["document_id"], text,
                            metadata | {"file_name": document["file_name"]},
                            file_name=document["file_name"], document_id=job["document_id"],
                            authorize=lambda conn: queue.validate(conn, claim),
                        )
                active.append(job)
            except LeaseLost:
                raise
            except Exception as exc:  # noqa: BLE001 - persist safe per-document failure
                code = "extraction_failed"
                if isinstance(exc, IngestionError) and "no embedded text" in str(exc):
                    code = "pdf_requires_ocr"
                elif isinstance(exc, UnicodeError):
                    code = "text_encoding_invalid"
                elif str(exc) in {"original_hash_mismatch", "extracted_text_too_large", "invalid_upload_path"}:
                    code = str(exc)
                fail(job, code)
        if not active:
            return True
        snapshot = canonical_snapshot(config, project)
        if snapshot["excluded_document_ids"]:
            raise ValueError("corpus_text_incomplete")
        provider = embedding_provider_for_project(config, project)
        provenance = provider.resolve()
        vectors = Neo4jVectorStore(config, snapshot, provenance, write_guard=lambda: queue.fence(claim))
        try:
            by_document = {}
            for row in snapshot["rows"]:
                by_document.setdefault(row["document_id"], set()).add(row["id"])

            def progress(valid):
                for job in active:
                    ids = by_document.get(job["document_id"], set())
                    queue.update(claim, job["document_id"], stage="embedding", chunk_count=len(ids), vector_count=len(ids & valid))

            vectors.build(provider, batch_size=int(config.get("EMBEDDING_BATCH_SIZE", 16)), progress=progress)
            for job in active:
                queue.update(claim, job["document_id"], stage="publishing")
            # An upload arriving mid-build changes the manifest; never publish it as indexed.
            if canonical_snapshot(config, project)["manifest"] != snapshot["manifest"]:
                raise ValueError("corpus_changed")
            vectors.publish()
            for job in active:
                queue.update(claim, job["document_id"], stage="graph")
            try:
                extractor = graph_extractor_for_project(config, vectors.key)
                graph = EvidenceGraph(vectors, extractor.profile)
                graph.build(
                    extractor,
                    max_chunks=int(config.get("GRAPH_EXTRACTION_MAX_CHUNKS", 0)),
                )
                if canonical_snapshot(config, project)["manifest"] != snapshot["manifest"]:
                    raise ValueError("corpus_changed")
                graph.publish()
            except Exception:
                logging.getLogger(__name__).exception("Graph indexing unavailable")
            for job in active:
                queue.update(claim, job["document_id"], state="completed", stage="completed")
        finally:
            vectors.close()
    except LeaseLost:
        pass
    except Exception:  # noqa: BLE001 - durable retry; never expose provider details
        for job in active:
            try:
                fail(job, "indexing_unavailable")
            except LeaseLost:
                break
    finally:
        stopped.set()
        thread.join(timeout=2)
        queue.release(claim)
    return True
