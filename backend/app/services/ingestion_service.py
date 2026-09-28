import json
import re
import time
from pathlib import Path

import httpx
from pypdf import PdfReader

from ai.graph.extractor import (
    extract_fallback_entities,
    fallback_relations,
    graph_extraction_prompt,
    graph_json_stats,
    parse_graph_json,
)
from ai.graph.store import Neo4jGraphStore
from ai.ingestion.chunker import TextChunker, clean_ocr_for_graph
from ai.ingestion.unstructured_client import UnstructuredClient
from backend.app.db.connection import connect, db
from backend.app.db.repository import SimpleRepository, now_ms
from backend.app.services.crypto import SecretBox
from backend.app.services.embedding_service import embedding_provider_for_project
from backend.app.services.llm_client import graph_extraction_llm
from backend.app.services.vector_store import TursoVectorStore


class IngestionError(Exception):
    pass


def sql_identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise IngestionError(f"Invalid SQL identifier: {value}")
    return value


class IngestionService:
    def __init__(self, app_config: dict):
        self.config = app_config
        self.documents = SimpleRepository(
            app_config["TURSO_DATABASE_URL"],
            app_config["TURSO_AUTH_TOKEN"],
            "documents",
            "doc",
        )

    def update_document_status(
        self, document_id: str, organization_id: str, status: str
    ) -> None:
        print(f"ingest {document_id} status={status}", flush=True)
        with db(
            self.config["TURSO_DATABASE_URL"], self.config["TURSO_AUTH_TOKEN"]
        ) as conn:
            conn.execute(
                "UPDATE documents SET status = ?, updated_at = ? WHERE id = ? AND organization_id = ?",
                (status, now_ms(), document_id, organization_id),
            )

    def ingest_uploaded_file(
        self, project: dict, document: dict, file_path: Path
    ) -> dict:
        try:
            print(
                f"ingest {document['id']} begin file={file_path.name} size_bytes={file_path.stat().st_size}",
                flush=True,
            )
            self.update_document_status(
                document["id"], project["organization_id"], "extracting_text"
            )
            started = time.monotonic()
            text = self.extract_text(file_path)
            print(
                f"ingest {document['id']} extracted text chars={len(text)} words={len(text.split())} "
                f"duration={time.monotonic() - started:.1f}s",
                flush=True,
            )
            return self.ingest_text(project, document, text)
        except Exception as exc:
            self.update_document_status(
                document["id"], project["organization_id"], "failed"
            )
            print(f"ingest {document['id']} failed error={exc}", flush=True)
            raise IngestionError(str(exc)) from exc

    def ingest_text(self, project: dict, document: dict, text: str) -> dict:
        if not text.strip():
            raise IngestionError("No OCR text was extracted for this document")
        self.update_document_status(
            document["id"], project["organization_id"], "chunking"
        )
        started = time.monotonic()
        chunks = TextChunker().chunk(text)
        print(
            f"ingest {document['id']} chunked chunks={len(chunks)} "
            f"duration={time.monotonic() - started:.1f}s",
            flush=True,
        )
        if not chunks:
            raise IngestionError("Document text did not produce any chunks")

        self.embed_chunks(project, document, chunks)

        graph_text = clean_ocr_for_graph(text)
        print(
            f"ingest {document['id']} graph_text_cleaned original_chars={len(text)} cleaned_chars={len(graph_text)} "
            f"removed_chars={len(text) - len(graph_text)}",
            flush=True,
        )
        graph_chunks = TextChunker(
            int(self.config.get("GRAPH_CHUNK_SIZE", 350)),
            int(self.config.get("GRAPH_CHUNK_OVERLAP", 40)),
        ).chunk(graph_text)
        self.update_document_status(
            document["id"], project["organization_id"], "extracting_graph"
        )
        started = time.monotonic()
        entities, relations = self.extract_graph(graph_chunks)
        print(
            f"ingest {document['id']} extracted graph entities={len(entities)} relations={len(relations)} "
            f"duration={time.monotonic() - started:.1f}s",
            flush=True,
        )

        self.update_document_status(
            document["id"], project["organization_id"], "indexing_graph"
        )
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
        print(
            f"ingest {document['id']} indexed graph duration={time.monotonic() - started:.1f}s",
            flush=True,
        )
        self.update_document_status(document["id"], project["organization_id"], "ready")
        print(f"ingest {document['id']} done status=ready", flush=True)
        return self.documents.get(document["id"], project["organization_id"])

    def ingest_text_chunks_only(self, project: dict, document: dict, text: str) -> dict:
        if not text.strip():
            raise IngestionError("No OCR text was extracted for this document")
        self.update_document_status(
            document["id"], project["organization_id"], "chunking"
        )
        started = time.monotonic()
        chunks = TextChunker().chunk(text)
        print(
            f"ingest {document['id']} chunked chunks={len(chunks)} "
            f"duration={time.monotonic() - started:.1f}s graph=skipped",
            flush=True,
        )
        if not chunks:
            raise IngestionError("Document text did not produce any chunks")

        self.embed_chunks(project, document, chunks)

        self.update_document_status(
            document["id"], project["organization_id"], "indexing_chunks"
        )
        store = Neo4jGraphStore(
            self.config["NEO4J_URI"],
            self.config["NEO4J_USERNAME"],
            self.config["NEO4J_PASSWORD"],
        )
        try:
            store.ensure_constraints()
            store.ingest_document(project, document, chunks, [], [])
        finally:
            store.close()
        self.update_document_status(document["id"], project["organization_id"], "ready")
        print(f"ingest {document['id']} done status=ready graph=skipped", flush=True)
        return self.documents.get(document["id"], project["organization_id"])

    def embed_chunks(self, project: dict, document: dict, chunks: list) -> None:
        self.update_document_status(
            document["id"], project["organization_id"], "embedding"
        )
        provider = embedding_provider_for_project(self.config, project)
        store = TursoVectorStore(
            self.config["TURSO_DATABASE_URL"], self.config["TURSO_AUTH_TOKEN"]
        )
        batch_size = max(1, int(self.config.get("EMBEDDING_BATCH_SIZE", 16)))
        rows = [
            {
                "id": f"chunk:{document['id']}:{chunk.chunk_index}",
                "document_id": document["id"],
                "content": chunk.content,
            }
            for chunk in chunks
        ]
        started = time.monotonic()
        for offset in range(0, len(rows), batch_size):
            batch = rows[offset : offset + batch_size]
            vectors = provider.embed_texts([row["content"] for row in batch])
            store.upsert(project, batch, vectors)
        print(
            f"ingest {document['id']} embedded chunks={len(rows)} model=google/embeddinggemma-300m "
            f"duration={time.monotonic() - started:.1f}s",
            flush=True,
        )

    def extract_text(self, file_path: Path) -> str:
        suffix = file_path.suffix.lower()
        print(f"extract_text file={file_path.name} suffix={suffix}", flush=True)
        if suffix in {".txt", ".md", ".csv", ".json"}:
            return file_path.read_text(encoding="utf-8", errors="ignore")
        if suffix == ".pdf":
            text = self.extract_pdf_text(file_path)
            if text.strip():
                return text
            if self.config.get("UNSTRUCTURED_API_KEY") and self.config.get(
                "UNSTRUCTURED_API_URL"
            ):
                return self.extract_with_unstructured(file_path)
            raise IngestionError(
                "PDF has no embedded text and OCR service is not configured"
            )
        raise IngestionError(f"Unsupported document type: {suffix or 'unknown'}")

    def extract_pdf_text(self, file_path: Path) -> str:
        reader = PdfReader(str(file_path))
        print(
            f"extract_pdf file={file_path.name} pages={len(reader.pages)}", flush=True
        )
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
        job_id = client.create_parse_job(
            [file_path], self.config.get("UNSTRUCTURED_PARTITION_STRATEGY", "hi_res")
        )
        job = client.wait_for_job(job_id)
        output = job.get("output") or []
        file_id = (
            output[0].get("file_id")
            if output and isinstance(output[0], dict)
            else file_path.name
        )
        return client.elements_to_text(client.download_output(job_id, file_id))

    def extract_graph(self, chunks: list) -> tuple[list, list]:
        llm = graph_extraction_llm(self.config)
        entities = []
        relations = []
        configured_max_chunks = int(
            self.config.get("GRAPH_EXTRACTION_MAX_CHUNKS", 0) or 0
        )
        max_chunks = configured_max_chunks if configured_max_chunks > 0 else len(chunks)
        attempted_text = []
        print(
            f"graph_extract chunks_total={len(chunks)} chunks_attempted={min(len(chunks), max_chunks)} "
            f"timeout_seconds={self.config.get('GRAPH_LLM_TIMEOUT_SECONDS') or 'none'} model={self.config.get('GRAPH_LLM_MODEL')}",
            flush=True,
        )
        for attempt, chunk in enumerate(chunks[:max_chunks], start=1):
            attempted_text.append(chunk.content)
            started = time.monotonic()
            prompt_started = time.monotonic()
            prompt = graph_extraction_prompt(chunk.content)
            prompt_duration = time.monotonic() - prompt_started
            print(
                f"graph_extract chunk={attempt}/{min(len(chunks), max_chunks)} tokens={chunk.token_count} "
                f"chars={len(chunk.content)} prompt_chars={len(prompt)} prompt_build={prompt_duration:.3f}s start",
                flush=True,
            )
            try:
                ollama_started = time.monotonic()
                raw = llm.generate(prompt)
                ollama_duration = time.monotonic() - ollama_started
                print(
                    f"graph_extract chunk={attempt} ollama_done chars={len(raw)} ollama_duration={ollama_duration:.1f}s duration={time.monotonic() - started:.1f}s",
                    flush=True,
                )
            except httpx.TimeoutException as exc:
                print(
                    f"graph_extract chunk={attempt} timeout duration={time.monotonic() - started:.1f}s "
                    f"action=skip_chunk_and_continue error={exc}",
                    flush=True,
                )
                continue
            except httpx.HTTPError as exc:
                print(
                    f"graph_extract chunk={attempt} http_error duration={time.monotonic() - started:.1f}s error={exc}",
                    flush=True,
                )
                continue
            try:
                parse_started = time.monotonic()
                chunk_entities, chunk_relations = parse_graph_json(raw)
            except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                preview = raw.replace("\n", " ")[:500]
                print(
                    f"graph_extract chunk={attempt} parse_failed error={exc} raw_preview={preview}",
                    flush=True,
                )
                continue
            parse_duration = time.monotonic() - parse_started
            stats = graph_json_stats(raw)
            print(
                f"graph_extract chunk={attempt} parsed entities={len(chunk_entities)} relations={len(chunk_relations)} "
                f"raw_entities={stats['raw_entities']} raw_relations={stats['raw_relations']} "
                f"discarded_placeholder_entities={stats['placeholder_entities']} "
                f"discarded_placeholder_relations={stats['placeholder_relations']} "
                f"total_entities={len(entities) + len(chunk_entities)} total_relations={len(relations) + len(chunk_relations)} "
                f"parse_duration={parse_duration:.3f}s",
                flush=True,
            )
            if not chunk_entities and not chunk_relations:
                preview = raw.replace("\n", " ")[:500]
                print(
                    f"graph_extract chunk={attempt} parsed_empty raw_preview={preview}",
                    flush=True,
                )
            entities.extend(chunk_entities)
            relations.extend(chunk_relations)
            print(
                f"graph_extract progress chunks_done={attempt}/{min(len(chunks), max_chunks)} "
                f"elapsed={time.monotonic() - started:.1f}s cumulative_entities={len(entities)} cumulative_relations={len(relations)}",
                flush=True,
            )
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
    def __init__(self, app_config: dict):
        super().__init__(app_config)
        self.sources = SimpleRepository(
            app_config["TURSO_DATABASE_URL"],
            app_config["TURSO_AUTH_TOKEN"],
            "data_sources",
            "src",
        )

    def update_source_metadata(self, source: dict, metadata: dict, **updates) -> dict:
        metadata = metadata | updates
        updated = self.sources.update(
            source["id"],
            source["organization_id"],
            {"prefix": json.dumps(metadata)},
        )
        return json.loads((updated or source).get("prefix") or "{}")

    def fetch_batch(self, source: dict, metadata: dict, limit: int) -> list[dict]:
        token = SecretBox(self.config["CREDENTIAL_ENCRYPTION_KEY"]).decrypt(
            source["encrypted_secret_access_key"]
        )
        table = sql_identifier(metadata["table_name"])
        id_column = sql_identifier(metadata["id_column"])
        text_column = sql_identifier(metadata["text_column"])
        status_column = sql_identifier(metadata.get("status_column") or "ocr_status")
        status_value = metadata.get("status_value") or "done"
        last_source_id = metadata.get("last_source_id")
        where = f"WHERE {status_column} = ? AND {text_column} IS NOT NULL"
        params: list = [status_value]
        if last_source_id is not None:
            where += f" AND {id_column} > ?"
            params.append(last_source_id)
        params.append(limit)
        print(
            f"turso_ocr source={source['id']} source_read SELECT table={table} id_column={id_column} "
            f"text_column={text_column} limit={limit} last_source_id={last_source_id}",
            flush=True,
        )
        conn = connect(source["endpoint_url"], token)
        try:
            cursor = conn.execute(
                f"""
                SELECT {id_column} AS source_id, {text_column} AS ocr_text
                FROM {table}
                {where}
                ORDER BY {id_column}
                LIMIT ?
                """,
                tuple(params),
            )
            return [
                dict(
                    zip([column[0] for column in cursor.description], row, strict=True)
                )
                for row in cursor.fetchall()
            ]
        finally:
            conn.close()

    def run_background_ingestion(self, project: dict, source: dict) -> None:
        metadata = json.loads(source.get("prefix") or "{}")
        batch_size = min(max(int(metadata.get("batch_size") or 50), 1), 500)
        max_documents = metadata.get("max_documents")
        max_documents = int(max_documents) if max_documents is not None else None
        skip_graph = bool(metadata.get("skip_graph_extraction", False))
        processed = int(metadata.get("processed_count") or 0)
        completed = int(metadata.get("completed_count") or 0)
        failed = int(metadata.get("failed_count") or 0)
        metadata = self.update_source_metadata(
            source,
            metadata,
            ingestion_status="running",
            ingestion_started_at=metadata.get("ingestion_started_at") or now_ms(),
            ingestion_finished_at=None,
            last_error=None,
        )
        print(
            f"turso_ocr source={source['id']} ingestion start batch_size={batch_size} "
            f"max_documents={max_documents} graph={'skipped' if skip_graph else 'enabled'}",
            flush=True,
        )
        try:
            while max_documents is None or processed < max_documents:
                limit = (
                    batch_size
                    if max_documents is None
                    else min(batch_size, max_documents - processed)
                )
                rows = self.fetch_batch(source, metadata, limit)
                if not rows:
                    break
                for row in rows:
                    source_id = row["source_id"]
                    processed += 1
                    doc_started = time.monotonic()
                    text = str(row["ocr_text"] or "")
                    print(
                        f"turso_ocr source={source['id']} document_start source_id={source_id} "
                        f"batch_index={processed} text_chars={len(text)} graph={'skipped' if skip_graph else 'enabled'}",
                        flush=True,
                    )
                    document = self.documents.create(
                        {
                            "project_id": project["id"],
                            "organization_id": project["organization_id"],
                            "uploaded_by_user_id": project["owner_user_id"],
                            "file_name": str(source_id),
                            "status": "pending_processing",
                        }
                    )
                    try:
                        if skip_graph:
                            self.ingest_text_chunks_only(project, document, text)
                        else:
                            self.ingest_text(project, document, text)
                        completed += 1
                        print(
                            f"turso_ocr source={source['id']} document_done source_id={source_id} "
                            f"document_id={document['id']} duration={time.monotonic() - doc_started:.1f}s",
                            flush=True,
                        )
                    except Exception as exc:  # noqa: BLE001
                        failed += 1
                        self.update_document_status(
                            document["id"], project["organization_id"], "failed"
                        )
                        metadata = self.update_source_metadata(
                            source, metadata, last_error=f"{source_id}: {exc}"
                        )
                        print(
                            f"turso_ocr source={source['id']} document={source_id} failed error={exc}",
                            flush=True,
                        )
                    metadata = self.update_source_metadata(
                        source,
                        metadata,
                        last_source_id=source_id,
                        processed_count=processed,
                        completed_count=completed,
                        failed_count=failed,
                    )
                print(
                    f"turso_ocr source={source['id']} progress processed={processed} completed={completed} failed={failed}",
                    flush=True,
                )
            status = "completed" if failed == 0 else "completed_with_errors"
            metadata = self.update_source_metadata(
                source,
                metadata,
                ingestion_status=status,
                ingestion_finished_at=now_ms(),
            )
            print(
                f"turso_ocr source={source['id']} ingestion {status} processed={processed} completed={completed} failed={failed}",
                flush=True,
            )
        except Exception as exc:  # noqa: BLE001
            self.update_source_metadata(
                source,
                metadata,
                ingestion_status="failed",
                ingestion_finished_at=now_ms(),
                processed_count=processed,
                completed_count=completed,
                failed_count=failed,
                last_error=str(exc),
            )
            print(
                f"turso_ocr source={source['id']} ingestion failed error={exc}",
                flush=True,
            )

    def ingest_source(self, project: dict, source: dict) -> list[dict]:
        self.run_background_ingestion(project, source)
        return []
