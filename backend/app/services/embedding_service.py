import math

import httpx


def validate_vectors(vectors, count, dimensions=768):
    if not isinstance(vectors, list) or len(vectors) != count:
        raise ValueError("Embedding response count mismatch")
    for vector in vectors:
        if (not isinstance(vector, list) or len(vector) != dimensions
                or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in vector)
                or not any(vector)):
            raise ValueError("Embedding must be finite, nonzero and dimension-compatible")
    return vectors


class EmbeddingGemmaProvider:
    def __init__(self, base_url, model):
        self.base_url, self.model = base_url.rstrip("/"), model

    def embed_texts(self, texts):
        if not texts:
            return []
        if any(not isinstance(text, str) or not text.strip() for text in texts):
            raise ValueError("Embedding inputs must contain text")
        response = httpx.post(
            self.base_url + "/api/embed", json={"model": self.model, "input": texts, "truncate": False}, timeout=120,
        )
        response.raise_for_status()
        return validate_vectors(response.json().get("embeddings"), len(texts))

    def embed_query(self, text):
        return self.embed_texts([text])[0]


def embedding_provider_for_project(
    config: dict, project: dict
) -> EmbeddingGemmaProvider:
    return EmbeddingGemmaProvider(
        config["OLLAMA_BASE_URL"], config["OLLAMA_EMBEDDING_MODEL"]
    )
