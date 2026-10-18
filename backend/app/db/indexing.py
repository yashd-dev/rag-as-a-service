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
                             ("empty_source_text" if not text.strip() else type(exc).__name__, now_ms(), generation, lease))
                conn.execute("UPDATE documents SET status='failed', updated_at=? WHERE id=? AND EXISTS (SELECT 1 FROM index_generations WHERE id=? AND lease_token=?)",
                             (now_ms(), doc_id, generation, lease))
            raise
        return plan | {"state": "text_ready", "chunk_count": len(chunks)}
