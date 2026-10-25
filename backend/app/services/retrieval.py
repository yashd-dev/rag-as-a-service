"""Published Neo4j retrieval modes, rank fusion and canonical evidence budgets."""

import json
import math
import time
from contextlib import contextmanager

import httpx
from neo4j.exceptions import DriverError, Neo4jError

from backend.app.db.indexing import IndexRepository
from backend.app.services.embedding_service import embedding_provider_for_project
from backend.app.services.evidence_graph import EvidenceGraph
from backend.app.services.graph_extraction import graph_extractor_for_project
from backend.app.services.neo4j_vectors import Neo4jVectorStore, canonical_snapshot

MODES = {"vector", "graph", "hybrid"}
MAX_EVIDENCE_BYTES = 5000


class RetrievalUnavailable(RuntimeError):
    def __init__(self, code, status=409):
        super().__init__(code)
        self.code, self.status = code, status


def rank_candidates(mode, vector_items, graph_items, rows):
    expected = {row["id"]: row for row in rows}
    candidates = {}
    graph_items = sorted(
        graph_items, key=lambda item: item["method"] != "graph_expansion"
    )
    for items, source in ((vector_items, "vector"), (graph_items, "graph")):
        seen = set()
        for rank, item in enumerate(items, 1):
            chunk = item["chunk"]
            canonical = expected.get(chunk["id"])
            if not canonical or any(
                chunk.get(key) != canonical[key]
                for key in (
                    "document_id",
                    "generation_id",
                    "content",
                    "content_hash",
                    "start_char",
                    "end_char",
                )
            ):
                raise ValueError("Foreign or stale retrieval candidate")
            if chunk["id"] in seen:
                continue
            seen.add(chunk["id"])
            score = item.get("score")
            if score is not None and (
                isinstance(score, bool)
                or not isinstance(score, (int, float))
                or not math.isfinite(score)
                or not 0 <= score <= 1
            ):
                raise ValueError("Invalid vector score")
            method = "vector" if source == "vector" else item["method"]
            if method not in {"vector", "vector_seed", "graph_expansion"} or (
                method == "graph_expansion" and not item.get("path")
            ):
                raise ValueError("Invalid retrieval method")
            if (method == "graph_expansion") != (score is None):
                raise ValueError("Invalid retrieval score attribution")
            candidate = candidates.setdefault(
                chunk["id"],
                {
                    "chunk": canonical,
                    "vector_score": None,
                    "fusion_score": None,
                    "methods": [],
                    "path": [],
                },
            )
            candidate["methods"].append(method)
            if score is not None:
                candidate["vector_score"] = score
            if item.get("path"):
                candidate["path"] = item["path"]
            if mode == "hybrid":
                candidate["fusion_score"] = (candidate["fusion_score"] or 0) + 1 / (
                    60 + rank
                )
    result = list(candidates.values())
    return (
        sorted(result, key=lambda item: -item["fusion_score"])
        if mode == "hybrid"
        else result
    )


def select_context(candidates, mode, byte_budget=MAX_EVIDENCE_BYTES):
    """Keep whole passages; graph modes must include a complete connected path."""
    selected, by_id = [], {item["chunk"]["id"]: item for item in candidates}

    def fits(items):
        evidence = [
            {"id": "S" + str(index + 1), "text": item["chunk"]["content"]}
            for index, item in enumerate(items)
        ]
        return (
            len(items) <= 8
            and len(json.dumps(evidence, ensure_ascii=False).encode("utf-8"))
            <= byte_budget
        )

    if mode in {"graph", "hybrid"}:
        for item in candidates:
            if not item["path"]:
                continue
            if item["path"][-1]["chunk_id"] != item["chunk"]["id"] or any(
                previous["chunk_id"] != following["from_chunk_id"]
                for previous, following in zip(item["path"], item["path"][1:])
            ):
                raise ValueError("Disconnected graph path")
            ids = list(
                dict.fromkeys(
                    chunk_id
                    for edge in item["path"]
                    for chunk_id in (edge["from_chunk_id"], edge["chunk_id"])
                )
            )
            if any(chunk_id not in by_id for chunk_id in ids):
                raise ValueError("Graph path passage missing")
            bundle = [by_id[chunk_id] for chunk_id in ids]
            if fits(bundle):
                selected = bundle
                break
        if not selected and mode == "graph":
            return []
    for item in candidates:
        if item not in selected and fits([*selected, item]):
            selected.append(item)
    return selected


class RetrievalService:
    def __init__(self, config, project):
        self.config = {
            "OLLAMA_BASE_URL": "http://localhost:11434",
            "OLLAMA_EMBEDDING_MODEL": "embeddinggemma",
            "GRAPH_LLM_MODEL": "smollm2:135m",
            **config,
        }
        self.project = project

    def base_status(self):
        return IndexRepository(self.config).corpus_readiness(self.project)

    @contextmanager
    def stores(self):
        if not all(
            self.config.get(key)
            for key in ("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD")
        ):
            raise RetrievalUnavailable("retrieval_not_configured")
        try:
            snapshot = canonical_snapshot(self.config, self.project)
        except ValueError:
            raise RetrievalUnavailable("canonical_not_ready") from None
        if not snapshot["rows"] or snapshot["excluded_document_ids"]:
            raise RetrievalUnavailable(
                "partial_index" if snapshot["excluded_document_ids"] else "no_index"
            )
        provider = embedding_provider_for_project(self.config, self.project)
        try:
            provenance = provider.revision()
        except (ValueError, httpx.HTTPError):
            raise RetrievalUnavailable("embedding_unavailable", 503) from None
        vectors = Neo4jVectorStore(self.config, snapshot, provenance)
        try:
            yield snapshot, provider, vectors
        except (DriverError, Neo4jError, httpx.HTTPError):
            raise RetrievalUnavailable("retrieval_unavailable", 503) from None
        finally:
            vectors.close()

    @staticmethod
    def require_vector(vectors):
        try:
            vectors.require_publication()
        except ValueError:
            raise RetrievalUnavailable("vector_not_ready") from None

    def graph(self, vectors):
        try:
            extractor = graph_extractor_for_project(self.config, vectors.key)
            graph = EvidenceGraph(vectors, extractor.profile)
        except (ValueError, httpx.HTTPError):
            raise RetrievalUnavailable("graph_not_ready") from None
        try:
            graph.require_publication()
        except ValueError:
            raise RetrievalUnavailable(
                "graph_partial" if graph.cached() else "graph_not_ready"
            ) from None
        return graph

    def retrieve(self, message, mode):
        if not isinstance(mode, str) or mode not in MODES:
            raise ValueError("Unsupported retrieval mode")
        base = self.base_status()
        if not base["capabilities"]["text"]:
            raise RetrievalUnavailable(
                "partial_index" if base["counts"]["total"] else "no_index"
            )
        started = time.perf_counter()
        with self.stores() as (snapshot, provider, vectors):
            self.require_vector(vectors)
            graph = self.graph(vectors) if mode != "vector" else None
            vector_items = (
                vectors.search(provider, message, limit=8) if mode != "graph" else []
            )
            graph_result = graph.search(provider, message) if graph else None
            try:
                candidates = rank_candidates(
                    mode,
                    vector_items,
                    graph_result["results"] if graph_result else [],
                    snapshot["rows"],
                )
                context = select_context(candidates, mode)
            except ValueError:
                raise RetrievalUnavailable("invalid_retrieval_evidence", 503) from None
            return {
                "candidates": candidates,
                "context": context,
                "partition": vectors.key,
                "graph_key": graph.key if graph else None,
                "canonical_manifest": snapshot["manifest"],
                "embedding": vectors.provenance,
                "diagnostics": {
                    "mode": mode,
                    "path": (
                        "neo4j_vector"
                        if mode == "vector"
                        else (
                            "semantic_seeds_then_evidence_graph"
                            if mode == "graph"
                            else "vector_and_graph_rrf"
                        )
                    ),
                    "ranking": (
                        "reciprocal_rank_fusion_k60"
                        if mode == "hybrid"
                        else "cosine" if mode == "vector" else "connected_graph_paths"
                    ),
                    "candidate_count": len(candidates),
                    "context_count": len(context),
                    "evidence_byte_budget": MAX_EVIDENCE_BYTES,
                    "graph_added": graph_result["graph_added"] if graph_result else 0,
                    "graph_strategy": (
                        getattr(graph, "profile", {}).get("strategy", "full_legal")
                        if graph
                        else None
                    ),
                    "retrieval_ms": round((time.perf_counter() - started) * 1000, 2),
                },
            }

    def verify(self, partition, graph_key, mode):
        with self.stores() as (_, _, vectors):
            if vectors.key != partition:
                raise RetrievalUnavailable("index_generation_changed")
            self.require_vector(vectors)
            if mode != "vector" and self.graph(vectors).key != graph_key:
                raise RetrievalUnavailable("graph_generation_changed")

    def status(self):
        base = self.base_status()
        if not base["capabilities"]["text"]:
            return base
        try:
            with self.stores() as (_, _, vectors):
                self.require_vector(vectors)
                base["capabilities"]["vector"] = True
                base["state"], base["vector_generation"] = "vector_ready", vectors.key
                graph = None
                try:
                    graph = self.graph(vectors)
                    base["capabilities"]["graph"] = True
                    base["state"], base["graph_generation"] = (
                        "graphrag_ready",
                        graph.key,
                    )
                    base["graph_extractor"] = getattr(graph, "profile", {})
                except RetrievalUnavailable as exc:
                    base["failures"] = [
                        {"stage": "graph", "code": exc.code, "retryable": True}
                    ]
                    if exc.code == "graph_partial":
                        base["state"] = "graph_partial"
                for item in base["documents"]:
                    item["capabilities"].update(vector=True, graph=graph is not None)
                    item["state"], item["retry_eligible"] = (
                        "graphrag_ready" if graph else "vector_ready"
                    ), graph is None
                    item["coverage"]["verified_vectors"] = item["coverage"][
                        "valid_chunks"
                    ]
                    item["coverage"]["verified_graph_chunks"] = (
                        item["coverage"]["valid_chunks"] if graph else 0
                    )
                    item["unavailable"] = [] if graph else ["graph_not_ready"]
                base["counts"]["text_ready"] = 0
                base["counts"]["graphrag_ready" if graph else "vector_ready"] = len(
                    base["documents"]
                )
        except RetrievalUnavailable as exc:
            base["capabilities"].update(vector=False, graph=False)
            base["state"] = "text_ready"
            base.pop("vector_generation", None)
            base.pop("graph_generation", None)
            base.pop("graph_extractor", None)
            base["failures"] = [
                {"stage": "vector", "code": exc.code, "retryable": True}
            ]
        return base
