import json
import re
import time
from pathlib import Path

import httpx
from pypdf import PdfReader

from ai.graph.extractor import extract_fallback_entities, fallback_relations, graph_extraction_prompt, parse_graph_json
from ai.graph.store import Neo4jGraphStore
from ai.ingestion.chunker import TextChunker
from ai.ingestion.unstructured_client import UnstructuredClient
from backend.app.db.connection import db
from backend.app.db.repository import SimpleRepository, now_ms
from backend.app.services.crypto import SecretBox
from backend.app.services.llm_client import graph_extraction_llm


class IngestionError(Exception):
    pass


def sql_identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise IngestionError(f"Invalid SQL identifier: {value}")
    return value


class IngestionService:
    def __init__(self, app_config: dict):
        self.config = app_config
        self.documents = SimpleRepository(app_config["TURSO_DATABASE_URL"], app_config["TURSO_AUTH_TOKEN"], "documents", "doc")

    def update_document_status(self, document_id: str, organization_id: str, status: str) -> None:
        print(f"ingest {document_id} status={status}", flush=True)
        with db(self.config["TURSO_DATABASE_URL"], self.config["TURSO_AUTH_TOKEN"]) as conn:
            conn.execute(
                "UPDATE documents SET status = ?, updated_at = ? WHERE id = ? AND organization_id = ?",
                (status, now_ms(), document_id, organization_id),
            )

    def ingest_uploaded_file(self, project: dict, document: dict, file_path: Path) -> dict:
        try:
            print(f"ingest {document['id']} begin file={file_path.name} size_bytes={file_path.stat().st_size}", flush=True)
            self.update_document_status(document["id"], project["organization_id"], "extracting_text")
            started = time.monotonic()
            text = self.extract_text(file_path)
            print(
                f"ingest {document['id']} extracted text chars={len(text)} words={len(text.split())} "
                f"duration={time.monotonic() - started:.1f}s",
                flush=True,
            )
            return self.ingest_text(project, document, text)
        except Exception as exc:
            self.update_document_status(document["id"], project["organization_id"], "failed")
            print(f"ingest {document['id']} failed error={exc}", flush=True)
            raise IngestionError(str(exc)) from exc

    def ingest_text(self, project: dict, document: dict, text: str) -> dict:
        if not text.strip():
            raise IngestionError("No OCR text was extracted for this document")
        self.update_document_status(document["id"], project["organization_id"], "chunking")
        started = time.monotonic()
        chunks = TextChunker().chunk(text)
        print(
            f"ingest {document['id']} chunked chunks={len(chunks)} "
            f"duration={time.monotonic() - started:.1f}s",
            flush=True,
        )
        if not chunks:
            raise IngestionError("Document text did not produce any chunks")

        self.update_document_status(document["id"], project["organization_id"], "extracting_graph")
        started = time.monotonic()
        entities, relations = self.extract_graph(chunks)
        print(
            f"ingest {document['id']} extracted graph entities={len(entities)} relations={len(relations)} "
            f"duration={time.monotonic() - started:.1f}s",
            flush=True,
        )

        self.update_document_status(document["id"], project["organization_id"], "indexing_graph")
        started = time.monotonic()
        store = Neo4jGraphStore(
            self.config["NEO4J_URI"],
            self.config["NEO4J_USERNAME"],
            self.config["NEO4J_PASSWORD"],
        )
        try:
            store.ensure_constraints()
            store.ingest_document(project, document, chunks, entities, relations)
        finally:
            store.close()
        print(f"ingest {document['id']} indexed graph duration={time.monotonic() - started:.1f}s", flush=True)
        self.update_document_status(document["id"], project["organization_id"], "ready")
        print(f"ingest {document['id']} done status=ready", flush=True)
        return self.documents.get(document["id"], project["organization_id"])

    def extract_text(self, file_path: Path) -> str:
        suffix = file_path.suffix.lower()
        print(f"extract_text file={file_path.name} suffix={suffix}", flush=True)
        if suffix in {".txt", ".md", ".csv", ".json"}:
            return file_path.read_text(encoding="utf-8", errors="ignore")
        if suffix == ".pdf":
            text = self.extract_pdf_text(file_path)
            if text.strip():
                return text
            if self.config.get("UNSTRUCTURED_API_KEY") and self.config.get("UNSTRUCTURED_API_URL"):
                return self.extract_with_unstructured(file_path)
            raise IngestionError("PDF has no embedded text and OCR service is not configured")
        raise IngestionError(f"Unsupported document type: {suffix or 'unknown'}")

    def extract_pdf_text(self, file_path: Path) -> str:
        reader = PdfReader(str(file_path))
        print(f"extract_pdf file={file_path.name} pages={len(reader.pages)}", flush=True)
        page_texts = []
        for index, page in enumerate(reader.pages, start=1):
            started = time.monotonic()
            text = page.extract_text() or ""
            print(
                f"extract_pdf page={index}/{len(reader.pages)} chars={len(text)} "
                f"duration={time.monotonic() - started:.1f}s",
                flush=True,
            )
            page_texts.append(text)
        return "\n\n".join(page_texts)

    def extract_with_unstructured(self, file_path: Path) -> str:
        client = UnstructuredClient(
            self.config["UNSTRUCTURED_API_KEY"],
            self.config["UNSTRUCTURED_API_URL"],
            int(self.config.get("UNSTRUCTURED_POLL_SECONDS", 10)),
        )
        job_id = client.create_parse_job([file_path], self.config.get("UNSTRUCTURED_PARTITION_STRATEGY", "hi_res"))
        job = client.wait_for_job(job_id)
        output = job.get("output") or []
        file_id = output[0].get("file_id") if output and isinstance(output[0], dict) else file_path.name
        return client.elements_to_text(client.download_output(job_id, file_id))

    def extract_graph(self, chunks: list) -> tuple[list, list]:
        llm = graph_extraction_llm(self.config)
        entities = []
        relations = []
        max_chunks = int(self.config.get("GRAPH_EXTRACTION_MAX_CHUNKS", 3))
        attempted_text = []
        print(
            f"graph_extract chunks_total={len(chunks)} chunks_attempted={min(len(chunks), max_chunks)} "
            f"timeout_seconds={self.config.get('GRAPH_LLM_TIMEOUT_SECONDS', 50)} model={self.config.get('GRAPH_LLM_MODEL')}",
            flush=True,
        )
        for attempt, chunk in enumerate(chunks[:max_chunks], start=1):
            attempted_text.append(chunk.content)
            started = time.monotonic()
            print(
                f"graph_extract chunk={attempt}/{min(len(chunks), max_chunks)} tokens={chunk.token_count} chars={len(chunk.content)} start",
                flush=True,
            )
            try:
                raw = llm.generate(graph_extraction_prompt(chunk.content))
                print(
                    f"graph_extract chunk={attempt} ollama_done chars={len(raw)} duration={time.monotonic() - started:.1f}s",
                    flush=True,
                )
            except httpx.TimeoutException as exc:
                print(f"graph_extract chunk={attempt} timeout duration={time.monotonic() - started:.1f}s error={exc}", flush=True)
                continue
            except httpx.HTTPError as exc:
                print(f"graph_extract chunk={attempt} http_error duration={time.monotonic() - started:.1f}s error={exc}", flush=True)
                continue
            try:
                chunk_entities, chunk_relations = parse_graph_json(raw)
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                preview = raw.replace("\n", " ")[:500]
                print(f"graph_extract chunk={attempt} parse_failed error={exc} raw_preview={preview}", flush=True)
                continue
            print(
                f"graph_extract chunk={attempt} parsed entities={len(chunk_entities)} relations={len(chunk_relations)}",
                flush=True,
            )
            entities.extend(chunk_entities)
            relations.extend(chunk_relations)
        if not entities:
            entities = extract_fallback_entities("\n".join(attempted_text))
            relations = fallback_relations(entities)
            print(f"graph_extract fallback_entities={len(entities)}", flush=True)
        elif not relations:
            relations = fallback_relations(entities)
            print(f"graph_extract fallback_relations={len(relations)}", flush=True)
        unique_entities = {entity.normalized_name: entity for entity in entities}
        return list(unique_entities.values()), relations


class TursoOcrIngestionService(IngestionService):
    def ingest_source(self, project: dict, source: dict) -> list[dict]:
        metadata = json.loads(source.get("prefix") or "{}")
        token = SecretBox(self.config["CREDENTIAL_ENCRYPTION_KEY"]).decrypt(source["encrypted_secret_access_key"])
        table = sql_identifier(metadata["table_name"])
        id_column = sql_identifier(metadata["id_column"])
        text_column = sql_identifier(metadata["text_column"])
        status_column = sql_identifier(metadata.get("status_column") or "ocr_status")
        status_value = metadata.get("status_value") or "done"
        with db(source["endpoint_url"], token) as conn:
            cursor = conn.execute(
                f"SELECT {id_column} AS source_id, {text_column} AS ocr_text FROM {table} WHERE {status_column} = ? AND {text_column} IS NOT NULL",
                (status_value,),
            )
            rows = [dict(zip([column[0] for column in cursor.description], row, strict=True)) for row in cursor.fetchall()]

        ingested = []
        for row in rows:
            document = self.documents.create(
                {
                    "project_id": project["id"],
                    "organization_id": project["organization_id"],
                    "uploaded_by_user_id": project["owner_user_id"],
                    "file_name": str(row["source_id"]),
                    "status": "pending_processing",
                }
            )
            try:
                ingested.append(self.ingest_text(project, document, str(row["ocr_text"] or "")))
            except IngestionError:
                ingested.append(self.documents.get(document["id"], project["organization_id"]))
        return ingested
