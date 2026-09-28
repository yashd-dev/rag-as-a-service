import pytest

from ai.embeddings.embeddinggemma import EMBEDDING_DIMENSIONS, EmbeddingGemmaProvider


def test_embeddinggemma_sends_batch_to_ollama(monkeypatch):
    requests = []

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "embeddings": [
                    [0.25] * EMBEDDING_DIMENSIONS,
                    [0.5] * EMBEDDING_DIMENSIONS,
                ]
            }

    def post(url, *, json, timeout):
        requests.append((url, json, timeout))
        return Response()

    monkeypatch.setattr("ai.embeddings.embeddinggemma.httpx.post", post)
    provider = EmbeddingGemmaProvider("http://ollama.test", "embeddinggemma:300m")

    assert provider.embed_texts(["first", "second"]) == [
        [0.25] * EMBEDDING_DIMENSIONS,
        [0.5] * EMBEDDING_DIMENSIONS,
    ]
    assert requests == [
        (
            "http://ollama.test/api/embed",
            {"model": "embeddinggemma:300m", "input": ["first", "second"]},
            60,
        )
    ]


def test_embeddinggemma_rejects_wrong_vector_dimension(monkeypatch):
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"embeddings": [[0.25] * 10]}

    monkeypatch.setattr(
        "ai.embeddings.embeddinggemma.httpx.post", lambda *_args, **_kwargs: Response()
    )
    provider = EmbeddingGemmaProvider("http://ollama.test", "embeddinggemma:300m")

    with pytest.raises(ValueError, match="unexpected count or dimension"):
        provider.embed_texts(["first"])
