"""Canonical input staging and retry ledger, independent of retrieval stores."""

import json
import uuid

from backend.app.db.connection import db
from backend.app.db.repository import now_ms
from backend.app.services.rag import CHUNKER_VERSION, TextChunker, fingerprint
from backend.inventory.sql import Reader, open_reader


class IdentityConflict(ValueError):
    pass


class IndexRepository:
    def __init__(self, config):
        self.url, self.token = config["TURSO_DATABASE_URL"], config["TURSO_AUTH_TOKEN"]
        self.recipe = {"chunker": CHUNKER_VERSION, "embedding_provider": "ollama",
                       "embedding_model": config.get("OLLAMA_EMBEDDING_MODEL", "embeddinggemma")}

    def record_failure(self, project, document, code):
        try:
            self.stage(project, "upload", document["id"], "", {"extraction_error": code},
                       file_name=document["file_name"], document_id=document["id"])
        except ValueError:
            pass  # Empty input has already persisted a failed generation.

    def readiness(self, project, document_id, reader=None):
        if reader is None:
            with open_reader(self.url, self.token) as connection:
                return self.readiness(project, document_id, connection)
        doc = reader.query("SELECT * FROM documents WHERE id=? AND project_id=? AND organization_id=?",
                           (document_id, project["id"], project["organization_id"]))
        if not doc:
            raise IdentityConflict("Document not found in project")
        schema_ready = bool(reader.query("SELECT name FROM sqlite_master WHERE name='document_sources' AND type='table'"))
        generations = reader.query(
            "SELECT g.* FROM document_sources s JOIN index_generations g ON g.id=s.current_generation "
            "WHERE s.document_id=? AND g.document_id=s.document_id AND s.organization_id=? AND s.project_id=? AND g.organization_id=? AND g.project_id=?",
            (document_id, project["organization_id"], project["id"], project["organization_id"], project["id"]),
        ) if schema_ready else []
        generation = generations[0] if generations else None
        chunks = reader.query("SELECT * FROM canonical_chunks WHERE generation_id=? ORDER BY chunk_index", (generation["id"],)) if generation else []
        return self._readiness(document_id, generation, chunks, schema_ready)

    def _readiness(self, document_id, generation, chunks, schema_ready):
        result = {"state": "pending", "capabilities": {"text": False, "vector": False, "graph": False},
                  "generation": None, "coverage": {"expected_chunks": None, "valid_chunks": 0, "verified_vectors": 0, "verified_graph_chunks": 0},
                  "verified_at": now_ms(), "failures": [], "retry_eligible": True,
                  "unavailable": ["neo4j_vectors_not_verified", "graph_retrieval_not_verified"]}
        if not schema_ready:
            result["failures"] = [{"stage": "metadata", "code": "migration_required", "retryable": False}]
            return result
        if generation is None:
            result["failures"] = [{"stage": "text", "code": "canonical_text_missing", "retryable": True}]
            return result
        expected = TextChunker().chunk(generation["source_text"])
        metadata = json.loads(generation["source_metadata"])
        valid = 0
        for actual, chunk in zip(chunks, expected):
            pages = [page for page in metadata.get("pages", []) if page["start"] < chunk.end and page["end"] > chunk.start]
            if (actual["id"] == "chk_" + fingerprint([generation["id"], chunk.chunk_index, chunk.content])
                    and actual["content"] == chunk.content and actual["content_hash"] == fingerprint(chunk.content)
                    and actual["start_char"] == chunk.start and actual["end_char"] == chunk.end
                    and actual["chunk_index"] == chunk.chunk_index and json.loads(actual["source_pages"]) == pages):
                valid += 1
        text_ready = (bool(expected) and valid == len(chunks) == len(expected)
                      and fingerprint(generation["source_text"]) == generation["content_hash"]
                      and generation["id"] == "gen_" + fingerprint([document_id, generation["source_text"], metadata, json.loads(generation["recipe_json"])]))
        result.update(generation=generation["id"], state=generation["state"], attempts=generation["attempts"],
                      source_observed_at=generation["created_at"], recipe=json.loads(generation["recipe_json"]))
        result["coverage"].update(expected_chunks=len(expected), valid_chunks=valid)
        result["capabilities"]["text"] = text_ready
        code = generation["error_code"]
        if generation["state"] == "processing" and generation["lease_until"] <= now_ms():
            result["state"], code = "failed", "interrupted"
        elif generation["state"] == "text_ready" and not text_ready:
            result["state"], code = "failed", "canonical_integrity_failed"
        elif generation["state"] not in {"pending", "processing", "text_ready", "failed", "graph_partial"}:
            result["state"], code = "failed", "unsupported_readiness_claim"
        if result["recipe"] != self.recipe or generation["chunker_version"] != CHUNKER_VERSION:
            result["state"], code = "pending", "recipe_changed"
        if code:
            result["failures"] = [{"stage": "graph" if result["state"] == "graph_partial" else "text", "code": code, "retryable": True}]
        result["retry_eligible"] = result["state"] not in {"processing", "text_ready"}
        return result

    def corpus_readiness(self, project):
        # shortcut: recompute staged text integrity on reads; use publication proofs before serving large indexed corpora.
        with open_reader(self.url, self.token) as reader:
            documents = reader.query("SELECT * FROM documents WHERE project_id=? AND organization_id=? ORDER BY id", (project["id"], project["organization_id"]))
            schema_ready = bool(reader.query("SELECT name FROM sqlite_master WHERE name='document_sources' AND type='table'"))
            params = (project["id"], project["organization_id"], project["id"], project["organization_id"])
            generations = reader.query(
                "SELECT g.* FROM index_generations g JOIN document_sources s ON s.current_generation=g.id AND s.document_id=g.document_id "
                "WHERE g.project_id=? AND g.organization_id=? AND s.project_id=? AND s.organization_id=?", params,
            ) if schema_ready else []
            chunks = reader.query(
                "SELECT c.* FROM canonical_chunks c JOIN index_generations g ON g.id=c.generation_id "
                "JOIN document_sources s ON s.current_generation=g.id AND s.document_id=g.document_id "
                "WHERE g.project_id=? AND g.organization_id=? AND s.project_id=? AND s.organization_id=? ORDER BY c.chunk_index", params,
            ) if schema_ready else []
        by_document = {generation["document_id"]: generation for generation in generations}
        by_generation = {}
        for chunk in chunks:
            by_generation.setdefault(chunk["generation_id"], []).append(chunk)
        items = []
        for doc in documents:
            generation = by_document.get(doc["id"])
            items.append({"document_id": doc["id"], **self._readiness(doc["id"], generation, by_generation.get(generation["id"], []) if generation else [], schema_ready)})
        text_ready = bool(items) and all(item["capabilities"]["text"] and item["state"] == "text_ready" for item in items)
        states = {state: sum(item["state"] == state for item in items) for state in ("pending", "processing", "text_ready", "failed", "graph_partial")}
        return {"scope": "all_application_documents", "project_id": project["id"], "organization_id": project["organization_id"],
                "generation": fingerprint([[item["document_id"], item["generation"]] for item in items]),
                "state": "text_ready" if text_ready else "failed" if states["failed"] else "graph_partial" if states["graph_partial"] else "processing" if states["processing"] else "pending",
                "capabilities": {"text": text_ready, "vector": False, "graph": False}, "counts": states | {"total": len(items), "excluded": 0},
                "documents": items, "verified_at": now_ms()}

    def _plan(self, reader, project, source_key, record_id, text, metadata, file_name, document_id):
        org, project_id = project["organization_id"], project["id"]
        if not reader.query("SELECT id FROM projects WHERE id = ? AND organization_id = ?", (project_id, org)):
            raise IdentityConflict("Project not found in organization")
        has_mapping = reader.query("SELECT name FROM sqlite_master WHERE type='table' AND name='document_sources'")
        mappings = reader.query(
            "SELECT * FROM document_sources WHERE organization_id = ? AND project_id = ? AND source_key = ? AND source_record_id = ?",
            (org, project_id, source_key, record_id),
        ) if has_mapping else []
        if mappings:
            chosen_id = mappings[0]["document_id"]
            if document_id and document_id != chosen_id:
                raise IdentityConflict("Source already belongs to another document")
        elif document_id:
            rows = reader.query("SELECT id FROM documents WHERE id = ? AND organization_id = ? AND project_id = ?", (document_id, org, project_id))
            if not rows:
                raise IdentityConflict("Document not found in project")
            chosen_id = document_id
        else:
            rows = reader.query("SELECT id FROM documents WHERE organization_id = ? AND project_id = ? AND file_name = ?", (org, project_id, file_name))
            if len(rows) > 1:
                raise IdentityConflict("Ambiguous legacy source match; explicit document review required")
            chosen_id = rows[0]["id"] if rows else "doc_" + fingerprint([org, project_id, source_key, record_id])
        if has_mapping:
            claimed = reader.query("SELECT * FROM document_sources WHERE document_id = ?", (chosen_id,))
            if claimed and (claimed[0]["source_key"], claimed[0]["source_record_id"]) != (source_key, record_id):
                raise IdentityConflict("Document already claimed by a different source")
        generation = "gen_" + fingerprint([chosen_id, text, metadata, self.recipe])
        return {"document_id": chosen_id, "generation": generation, "source_key": source_key,
                "source_record_id": record_id, "content_hash": fingerprint(text), "recipe": self.recipe}

    def stage(self, project, source_key, record_id, text, metadata=None, file_name=None, document_id=None, dry_run=False):
        if not isinstance(text, str):
            raise TypeError("Source text must be a string")
        record_id = json.dumps(record_id, ensure_ascii=False)
        metadata = metadata or {}
        file_name = file_name or record_id
        args = (project, source_key, record_id, text, metadata, file_name, document_id)
        if dry_run:
            with open_reader(self.url, self.token) as reader:
                plan = self._plan(reader, *args)
            return plan | {"dry_run": True, "chunk_count": len(TextChunker().chunk(text))}
        timestamp, lease = now_ms(), uuid.uuid4().hex
        # shortcut: 60s lease covers text staging only; add renewal before long-running embedding/extraction jobs.
        with db(self.url, self.token) as conn:
            conn.execute("BEGIN IMMEDIATE")
            plan = self._plan(Reader(conn), *args)
            doc_id, generation = plan["document_id"], plan["generation"]
            busy = conn.execute(
                "SELECT id FROM index_generations WHERE document_id = ? AND state = 'processing' AND lease_until > ?",
                (doc_id, timestamp),
            ).fetchone()
            if busy:
                return plan | {"state": "processing", "busy": True}
            conn.execute("UPDATE index_generations SET state='failed', error_code='interrupted', lease_token=NULL, lease_until=0 WHERE document_id=? AND state='processing'",
                         (doc_id,))
            conn.execute(
                "INSERT INTO documents(id, organization_id, project_id, uploaded_by_user_id, file_name, status, created_at, updated_at) "
                "VALUES(?,?,?,?,?,'pending',?,?) ON CONFLICT(id) DO NOTHING",
                (doc_id, project["organization_id"], project["id"], project["owner_user_id"], file_name, timestamp, timestamp),
            )
            conn.execute(
                "INSERT INTO document_sources VALUES(?,?,?,?,?,?) ON CONFLICT(document_id) DO UPDATE SET current_generation=excluded.current_generation",
                (doc_id, project["organization_id"], project["id"], source_key, record_id, generation),
            )
            previous = conn.execute("SELECT state FROM index_generations WHERE id = ?", (generation,)).fetchone()
            if previous and previous[0] == "text_ready":
                if not self.readiness(project, doc_id, Reader(conn))["capabilities"]["text"]:
                    raise ValueError("canonical_integrity_failed")
                conn.execute("UPDATE documents SET status='text_ready', updated_at=? WHERE id=?", (timestamp, doc_id))
                return plan | {"state": "text_ready", "unchanged": True}
            conn.execute(
                "INSERT INTO index_generations(id,document_id,organization_id,project_id,source_text,source_metadata,content_hash,chunker_version,recipe_json,state,attempts,lease_token,lease_until,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,'processing',1,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
                "state='processing', error_code=NULL, attempts=attempts+1, lease_token=excluded.lease_token, lease_until=excluded.lease_until, updated_at=excluded.updated_at",
                (generation, doc_id, project["organization_id"], project["id"], text, json.dumps(metadata), plan["content_hash"], CHUNKER_VERSION, json.dumps(self.recipe), lease, timestamp + 60000, timestamp, timestamp),
            )
            conn.execute("UPDATE documents SET status='processing', updated_at=? WHERE id=?", (timestamp, doc_id))
        try:
            chunks = TextChunker().chunk(text)
            if not chunks:
                raise ValueError("empty_source_text")
            with db(self.url, self.token) as conn:
                conn.execute("BEGIN IMMEDIATE")
                owner = conn.execute("SELECT lease_token FROM index_generations WHERE id=?", (generation,)).fetchone()
                if owner[0] != lease:
                    raise RuntimeError("generation_lease_lost")
                for chunk in chunks:
                    pages = [page for page in metadata.get("pages", []) if page["start"] < chunk.end and page["end"] > chunk.start]
                    conn.execute(
                        "INSERT INTO canonical_chunks VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO NOTHING",
                        ("chk_" + fingerprint([generation, chunk.chunk_index, chunk.content]), generation, chunk.chunk_index,
                         chunk.content, fingerprint(chunk.content), chunk.start, chunk.end, json.dumps(pages)),
                    )
                conn.execute("UPDATE index_generations SET state='text_ready', lease_until=0, updated_at=? WHERE id=?", (now_ms(), generation))
                conn.execute("UPDATE documents SET status='text_ready', updated_at=? WHERE id=?", (now_ms(), doc_id))
        except Exception as exc:
            with db(self.url, self.token) as conn:
                conn.execute("UPDATE index_generations SET state='failed', error_code=?, lease_until=0, updated_at=? WHERE id=? AND lease_token=?",
                             (metadata.get("extraction_error") or ("empty_source_text" if not text.strip() else type(exc).__name__), now_ms(), generation, lease))
                conn.execute("UPDATE documents SET status='failed', updated_at=? WHERE id=? AND EXISTS (SELECT 1 FROM index_generations WHERE id=? AND lease_token=?)",
                             (now_ms(), doc_id, generation, lease))
            raise
        return plan | {"state": "text_ready", "chunk_count": len(chunks)}
