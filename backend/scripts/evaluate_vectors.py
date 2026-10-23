"""Run frozen source-reviewed vector queries without generating an answer."""

import argparse
import json
import math
import os
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from dotenv import dotenv_values

from backend.app.services.embedding_service import EmbeddingGemmaProvider
from backend.app.services.neo4j_vectors import Neo4jVectorStore, canonical_snapshot


def lexical_baseline(rows, query, limit):
    """BM25, k1=1.5/b=0.75; same canonical corpus, no embeddings or inferred labels."""
    documents = [Counter(re.findall(r"\w+", row["content"].casefold())) for row in rows]
    document_frequency = Counter(token for document in documents for token in document)
    average_length = sum(sum(document.values()) for document in documents) / len(
        documents
    )
    ranked = []
    for row, document in zip(rows, documents, strict=True):
        score = 0
        for token in set(re.findall(r"\w+", query.casefold())):
            frequency = document[token]
            if frequency:
                inverse_frequency = math.log(
                    1
                    + (len(documents) - document_frequency[token] + 0.5)
                    / (document_frequency[token] + 0.5)
                )
                score += (
                    inverse_frequency
                    * frequency
                    * 2.5
                    / (
                        frequency
                        + 1.5 * (0.25 + 0.75 * sum(document.values()) / average_length)
                    )
                )
        ranked.append({"id": row["id"], "score": score})
    return sorted(ranked, key=lambda item: (-item["score"], item["id"]))[:limit]


def evaluate(store, provider, fixture):
    scope = fixture["scope"]
    if (
        scope["canonical_manifest"] != store.snapshot["manifest"]
        or scope["partition"] != store.key
        or any(
            scope[key] != store.provenance[key]
            for key in ("model", "revision", "dimensions")
        )
    ):
        raise ValueError("Frozen evaluation generation/model mismatch")
    chunks = {row["id"]: row for row in store.snapshot["rows"]}
    for case in fixture["cases"]:
        for chunk_id in case["expected_chunk_ids"]:
            actual = chunks[chunk_id]
            if (
                any(
                    actual[key] != case[key]
                    for key in (
                        "document_id",
                        "generation_id",
                        "content_hash",
                        "start_char",
                        "end_char",
                    )
                )
                or case["excerpt"] not in actual["content"]
            ):
                raise ValueError("Frozen expected source passage changed")
    results = []
    for case in fixture["cases"]:
        ranked = store.search(
            provider, case["query"], scope["top_k"], require_publication=False
        )
        ids = [item["chunk"]["id"] for item in ranked]
        expected = case["expected_chunk_ids"]
        ranks = [ids.index(chunk_id) + 1 for chunk_id in expected if chunk_id in ids]
        lexical = lexical_baseline(
            store.snapshot["rows"], case["query"], scope["top_k"]
        )
        results.append(
            {
                "id": case["id"],
                "query": case["query"],
                "expected_chunk_ids": expected,
                "passed": len(ranks) == len(expected)
                and (
                    not case.get("require_lexical_miss")
                    or not any(item["id"] in expected for item in lexical)
                ),
                "recall_at_k": len(ranks) / len(expected) if expected else None,
                "reciprocal_rank": 1 / min(ranks) if ranks else None,
                "lexical_baseline": {
                    "method": "BM25 k1=1.5 b=0.75 unicode-word-tokenization",
                    "ranked": lexical,
                    "expected_hits": sum(item["id"] in expected for item in lexical),
                },
                "control_note": (
                    None
                    if expected
                    else "Nearest neighbors are candidates only; no answer generated. Abstention is Stage E."
                ),
                "ranked": [
                    {
                        "score": item["score"],
                        "chunk": {
                            key: value
                            for key, value in item["chunk"].items()
                            if key != "source_metadata"
                        },
                    }
                    for item in ranked
                ],
            }
        )
    return {
        "scope": scope,
        "source_review": fixture["review"],
        "mode": "vector",
        "path": "neo4j_partitioned_vector_index",
        "answer_generated": False,
        "measured_at": datetime.now(UTC).isoformat(),
        "cases": results,
        "passed": all(item["passed"] for item in results)
        and fixture["review"]["decision"] == "approved_expected_passages",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path("backend/.env"))
    parser.add_argument(
        "--fixture", type=Path, default=Path("backend/evaluation/stage-c-v3.json")
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="NEW report path; never overwrite evidence",
    )
    args = parser.parse_args(argv)
    fixture = json.loads(args.fixture.read_text())
    config = dict(os.environ) | {
        key: value
        for key, value in dotenv_values(args.env_file).items()
        if value is not None
    }
    config["TURSO_DATABASE_URL"] = config.get("TURSO_DATABASE_URL") or config.get(
        "TURSO_CONNECTION_URL", ""
    )
    project = {
        "id": fixture["scope"]["project_id"],
        "organization_id": fixture["scope"]["organization_id"],
    }
    snapshot = canonical_snapshot(config, project)
    provider = EmbeddingGemmaProvider(
        config.get("OLLAMA_BASE_URL", "http://localhost:11434"),
        config.get("OLLAMA_EMBEDDING_MODEL", "embeddinggemma"),
    )
    store = Neo4jVectorStore(config, snapshot, provider.resolve())
    try:
        result = evaluate(store, provider, fixture)
        if canonical_snapshot(config, project) != snapshot:
            raise ValueError("Canonical input changed during evaluation")
        with args.output.open("x") as output:
            json.dump(result, output, indent=2, ensure_ascii=False)
            output.write("\n")
        print(
            json.dumps(
                {
                    "passed": result["passed"],
                    "output": str(args.output),
                    "cases": [
                        {key: value for key, value in case.items() if key != "ranked"}
                        for case in result["cases"]
                    ],
                }
            )
        )
        return 0 if result["passed"] else 2
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
