import pytest

from backend.app.services import embedding_service as embeddings
from backend.app.services.rag import TextChunker


def test_chunk_spans_cover_original_ocr_without_normalization():
    text = "  Case 123.\n\n" + "Article 21, protects liberty.\n" * 240 + "尾\x00end"
    chunks = TextChunker().chunk(text)
    assert len(chunks) > 1
    covered = set()
    for chunk in chunks:
        assert text[chunk.start:chunk.end] == chunk.content
        covered.update(range(chunk.start, chunk.end))
    assert all(i in covered for i, char in enumerate(text) if not char.isspace())


@pytest.mark.parametrize("vector", [[0] * 768, [1] * 767, [float("nan")] * 768, [True] * 768, ["1"] * 768])
def test_invalid_embeddings_are_rejected(vector):
    with pytest.raises(ValueError):
        embeddings.validate_vectors([vector], 1)


def test_provider_posts_actual_text_and_validates_count(monkeypatch):
    def post(url, *, json, timeout):
        assert url == "http://model/api/embed"
        assert json == {"model": "embeddinggemma", "input": ["actual passage"], "truncate": False}
        assert timeout == 120
        class Response:
            def raise_for_status(self):
                pass

            def json(self):
                return {"embeddings": [[1.0] * 768]}
        return Response()
    monkeypatch.setattr(embeddings.httpx, "post", post)
    assert len(embeddings.EmbeddingGemmaProvider("http://model/", "embeddinggemma").embed_query("actual passage")) == 768
    with pytest.raises(ValueError):
        embeddings.validate_vectors([], 1)


def test_graph_reads_are_scoped_bounded_and_never_write():
    from backend.app.services.graph_store import Neo4jGraphStore

    class Driver:
        def session(self, **kwargs):
            assert kwargs == {"default_access_mode": "READ"}
            return self

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def execute_read(self, callback):
            return callback(self)

        def run(self, query, **params):
            assert query.startswith("MATCH") and "LIMIT" in query
            assert params["project"] == "p" and params["org"] == "o"
            return self

        def data(self):
            return []

    store = Neo4jGraphStore.__new__(Neo4jGraphStore)
    store.driver = Driver()
    assert store.project_graph("p", "o") == {"nodes": [], "edges": [], "bounded": True}
    assert store.project_status("p", "o")["graph_ready"] is False
