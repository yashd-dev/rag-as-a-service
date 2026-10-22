from types import SimpleNamespace

import pytest

from backend.scripts.evaluate_vectors import evaluate, lexical_baseline


def test_lexical_baseline_uses_the_same_corpus_and_ranks_keyword_evidence():
    rows = [
        {"id": "unrelated", "content": "Employees receive wages for work."},
        {
            "id": "expected",
            "content": "The disputed handwriting was compared with admitted handwriting.",
        },
    ]
    assert lexical_baseline(rows, "disputed handwriting", 1)[0]["id"] == "expected"


def test_evaluation_fails_a_missing_expected_passage_and_a_changed_source():
    row = {
        "id": "expected",
        "document_id": "doc",
        "generation_id": "gen",
        "content_hash": "hash",
        "start_char": 0,
        "end_char": 8,
        "content": "evidence",
    }
    scope = {
        "canonical_manifest": "manifest",
        "partition": "partition",
        "model": "model",
        "revision": "revision",
        "dimensions": 768,
        "top_k": 8,
    }
    fixture = {
        "scope": scope,
        "review": {"decision": "approved_expected_passages"},
        "cases": [
            {
                "id": "paraphrase",
                "query": "source question",
                "expected_chunk_ids": ["expected"],
                "excerpt": "evidence",
                **{
                    key: value
                    for key, value in row.items()
                    if key not in {"id", "content"}
                },
            }
        ],
    }
    store = SimpleNamespace(
        snapshot={"manifest": "manifest", "rows": [row]},
        key="partition",
        provenance={key: scope[key] for key in ("model", "revision", "dimensions")},
        search=lambda *args, **kwargs: [],
    )
    result = evaluate(store, None, fixture)
    assert result["passed"] is False and result["cases"][0]["recall_at_k"] == 0
    row["content_hash"] = "changed"
    with pytest.raises(ValueError, match="source passage changed"):
        evaluate(store, None, fixture)
