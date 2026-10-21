"""Immutable, tenant/model/corpus-partitioned semantic indexes for Neo4j 5.26."""

import json

from neo4j import GraphDatabase, Query

from backend.app.db.indexing import IndexRepository
from backend.app.db.repository import now_ms
from backend.app.services.embedding_service import validate_vectors
from backend.app.services.rag import fingerprint
from backend.inventory.sql import open_reader


def canonical_snapshot(config, project):
    repository = IndexRepository(config)
    with open_reader(repository.url, repository.token) as reader:
        if not reader.query("SELECT id FROM projects WHERE id=? AND organization_id=?", (project["id"], project["organization_id"])):
            raise ValueError("Project not found in organization")
        documents = reader.query("SELECT * FROM documents WHERE project_id=? AND organization_id=? ORDER BY id",
                                 (project["id"], project["organization_id"]))
        generations = reader.query(
            "SELECT g.* FROM index_generations g JOIN document_sources s ON s.current_generation=g.id AND s.document_id=g.document_id "
            "WHERE g.project_id=? AND g.organization_id=? AND s.project_id=g.project_id AND s.organization_id=g.organization_id",
            (project["id"], project["organization_id"]),
        )
        chunks = reader.query(
            "SELECT c.* FROM canonical_chunks c JOIN index_generations g ON c.generation_id=g.id "
            "JOIN document_sources s ON s.current_generation=g.id AND s.document_id=g.document_id "
            "WHERE g.project_id=? AND g.organization_id=? AND s.project_id=g.project_id AND s.organization_id=g.organization_id ORDER BY c.chunk_index",
            (project["id"], project["organization_id"]),
        )
        by_document = {generation["document_id"]: generation for generation in generations}
        by_generation = {}
        for chunk in chunks:
            by_generation.setdefault(chunk["generation_id"], []).append(chunk)
        rows, excluded = [], []
        for document in documents:
            generation = by_document.get(document["id"])
            if generation is None:
                excluded.append(document["id"])
                continue
            document_chunks = by_generation.get(generation["id"], [])
            readiness = repository._readiness(document["id"], generation, document_chunks, True)
            if not readiness["capabilities"]["text"] or readiness["state"] != "text_ready":
                raise ValueError("Canonical generation is not text ready")
            for chunk in document_chunks:
                rows.append(chunk | {"document_id": document["id"], "file_name": document["file_name"],
                                     "source_metadata": generation["source_metadata"], "chunker_version": generation["chunker_version"]})
    return {"organization_id": project["organization_id"], "project_id": project["id"],
            "rows": rows, "excluded_document_ids": excluded, "manifest": fingerprint(rows)}


class Neo4jVectorStore:
    def __init__(self, config, snapshot, provenance):
        if provenance.get("provider") != "ollama" or provenance.get("dimensions") != 768:
            raise ValueError("Unsupported embedding provenance")
        self.snapshot, self.provenance = snapshot, provenance
        self.key = fingerprint([snapshot["organization_id"], snapshot["project_id"], snapshot["manifest"], provenance])
        # All interpolated identifiers are internally generated hexadecimal hashes.
        self.label, self.index = "RAGV_" + self.key, "ragv_" + self.key
        self.driver = GraphDatabase.driver(config["NEO4J_URI"], auth=(config["NEO4J_USERNAME"], config["NEO4J_PASSWORD"]))

    def close(self):
        self.driver.close()

    def _run(self, cypher, write=False, **params):
        with self.driver.session(default_access_mode="WRITE" if write else "READ") as session:
            return session.run(Query(cypher, timeout=120), **params).data()

    def prepare(self):
        if not self.snapshot["rows"]:
            raise ValueError("No canonical chunks to index")
        for label in ("RAGVectorChunk", "RAGVectorDocument", "RAGVectorPublication", "RAGVectorJob"):
            self._run(f"CREATE CONSTRAINT {label.lower()}_key IF NOT EXISTS FOR (n:{label}) REQUIRE n.key IS UNIQUE", write=True)
        self._run(f"CREATE VECTOR INDEX {self.index} IF NOT EXISTS FOR (c:{self.label}) ON c.embedding "
                  "OPTIONS {indexConfig: {`vector.dimensions`: 768, `vector.similarity_function`: 'cosine'}}", write=True)
        self._run("CALL db.awaitIndex($name, 120)", name=self.index)
        self.index_status()

    def index_status(self):
        rows = self._run("SHOW VECTOR INDEXES YIELD name, state, labelsOrTypes, properties, options WHERE name=$name RETURN *", name=self.index)
        if len(rows) != 1:
            raise ValueError("Vector index missing")
        index = rows[0]
        config = index["options"]["indexConfig"]
        if (index["state"] != "ONLINE" or index["labelsOrTypes"] != [self.label] or index["properties"] != ["embedding"]
                or config.get("vector.dimensions") != self.provenance["dimensions"] or str(config.get("vector.similarity_function")).lower() != "cosine"):
            raise ValueError("Vector index unavailable or incompatible")
        return index

    def records(self):
        with self.driver.session(default_access_mode="READ", fetch_size=128) as session:
            records = session.run(Query(f"MATCH (c:{self.label}) OPTIONAL MATCH (d:RAGVectorDocument)-[:CONTAINS]->(c) "
                                        "RETURN properties(c) AS chunk, collect(properties(d)) AS documents", timeout=120))
            for record in records:
                yield record.data()

    def valid_ids(self, complete=False):
        expected = {row["id"]: row for row in self.snapshot["rows"]}
        valid, seen = set(), set()
        for record in self.records():
            chunk, documents = record["chunk"], record["documents"]
            chunk_id = chunk.get("id")
            if chunk_id not in expected or chunk_id in seen:
                raise ValueError("Unexpected or duplicate vector chunk")
            seen.add(chunk_id)
            row = expected[chunk_id]
            try:
                validate_vectors([chunk.get("embedding")], 1, self.provenance["dimensions"])
                matches = (all(chunk.get(k) == v for k, v in self.properties(row).items())
                           and chunk.get("vector_hash") == fingerprint(chunk["embedding"])
                           and len(documents) == 1 and documents[0] == self.document_properties(row))
            except ValueError:
                matches = False
            if matches:
                valid.add(chunk_id)
        if complete and (not expected or valid != expected.keys()):
            raise ValueError("Incomplete vector coverage or integrity failure")
        return valid

    def document_properties(self, row):
        return {"key": fingerprint([self.key, row["document_id"], row["generation_id"]]),
                "id": row["document_id"], "generation_id": row["generation_id"], "partition": self.key,
                "organization_id": self.snapshot["organization_id"], "project_id": self.snapshot["project_id"]}

    def properties(self, row):
        return row | {"key": fingerprint([self.key, row["id"]]), "partition": self.key,
                      "organization_id": self.snapshot["organization_id"], "project_id": self.snapshot["project_id"],
                      "model": self.provenance["model"], "model_revision": self.provenance["revision"],
                      "embedding_provider": self.provenance["provider"], "dimensions": self.provenance["dimensions"]}

    def write_batch(self, rows, vectors):
        validate_vectors(vectors, len(rows), self.provenance["dimensions"])
        expected = {row["id"]: row for row in self.snapshot["rows"]}
        if any(expected.get(row["id"]) != row for row in rows):
            raise ValueError("Batch outside canonical snapshot")
        payload = [{"chunk": self.properties(row) | {"embedding": vector, "vector_hash": fingerprint(vector), "indexed_at": now_ms()},
                    "document": self.document_properties(row)} for row, vector in zip(rows, vectors, strict=True)]
        self._run("UNWIND $rows AS row MERGE (d:RAGVectorDocument {key: row.document.key}) SET d = row.document "
                  f"MERGE (c:RAGVectorChunk:{self.label} {{key: row.chunk.key}}) SET c = row.chunk "
                  "MERGE (d)-[:CONTAINS]->(c)", write=True, rows=payload)

    def checkpoint(self, state, completed, error=None):
        self._run("MERGE (j:RAGVectorJob {key:$key}) SET j.state=$state, j.completed=$completed, "
                  "j.error_code=$error, j.updated_at=$timestamp, j.organization_id=$org, j.project_id=$project",
                  write=True, key=self.key, state=state, completed=completed, error=error, timestamp=now_ms(),
                  org=self.snapshot["organization_id"], project=self.snapshot["project_id"])

    def build(self, provider, batch_size=16):
        if not 1 <= batch_size <= 64:
            raise ValueError("Batch size must be between 1 and 64")
        self.prepare()
        completed = 0
        try:
            valid = self.valid_ids()
            pending = [row for row in self.snapshot["rows"] if row["id"] not in valid]
            completed = len(valid)
            self.checkpoint("processing", completed)
            for offset in range(0, len(pending), batch_size):
                batch = pending[offset:offset + batch_size]
                vectors = provider.embed_versioned([row["content"] for row in batch], self.provenance)
                self.write_batch(batch, vectors)
                completed += len(batch)
                self.checkpoint("processing", completed)
            self.valid_ids(complete=True)
            self.index_status()
            self.checkpoint("verified_unpublished", completed)
            return {"partition": self.key, "expected_chunks": len(self.snapshot["rows"]), "verified_vectors": completed,
                    "reused_vectors": len(valid), "state": "verified_unpublished", "index": self.index}
        except Exception as exc:
            self.checkpoint("failed", completed, type(exc).__name__)
            raise

    def publish(self):
        self.valid_ids(complete=True)
        self.index_status()
        self._run("MERGE (p:RAGVectorPublication {key:$key}) SET p.manifest=$manifest, p.provenance=$provenance, "
                  "p.expected_chunks=$count, p.verified_at=$timestamp, p.organization_id=$org, p.project_id=$project",
                  write=True, key=self.key, manifest=self.snapshot["manifest"], provenance=json.dumps(self.provenance, sort_keys=True),
                  count=len(self.snapshot["rows"]), timestamp=now_ms(), org=self.snapshot["organization_id"], project=self.snapshot["project_id"])

    def withdraw(self):
        # Roll back availability only; retain vectors, canonical input and every other partition.
        self._run("MATCH (p:RAGVectorPublication {key:$key}) DELETE p", write=True, key=self.key)

    def search(self, provider, query, limit=8, require_publication=True):
        if not isinstance(query, str) or not query.strip() or not 1 <= limit <= 100:
            raise ValueError("Require a query and limit between 1 and 100")
        if require_publication:
            publication = self._run("MATCH (p:RAGVectorPublication {key:$key}) RETURN properties(p) AS publication", key=self.key)
            if len(publication) != 1 or any(publication[0]["publication"].get(k) != v for k, v in {
                "manifest": self.snapshot["manifest"], "provenance": json.dumps(self.provenance, sort_keys=True),
                "expected_chunks": len(self.snapshot["rows"]), "organization_id": self.snapshot["organization_id"],
                "project_id": self.snapshot["project_id"],
            }.items()):
                raise ValueError("Vector generation not published")
        self.index_status()
        self.valid_ids(complete=True)
        vector = provider.embed_versioned([query], self.provenance)[0]
        # Candidate selection is partitioned before top-k, not a global search followed by tenant filtering.
        result = self._run("CALL db.index.vector.queryNodes($index, $limit, $vector) YIELD node, score "
                           "RETURN properties(node) AS chunk, score ORDER BY score DESC",
                           index=self.index, limit=limit, vector=vector)
        expected = {row["id"]: row for row in self.snapshot["rows"]}
        for item in result:
            chunk = item["chunk"]
            if chunk.get("id") not in expected or any(chunk.get(k) != v for k, v in self.properties(expected[chunk["id"]]).items()):
                raise ValueError("Foreign or stale vector result")
            item["chunk"] = {k: v for k, v in chunk.items() if k not in {"embedding", "vector_hash"}}
        return result
