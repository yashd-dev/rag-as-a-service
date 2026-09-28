import httpx

from ai.embeddings.base import EmbeddingProvider

EMBEDDING_DIMENSIONS = 768
EMBEDDING_MODEL = "google/embeddinggemma-300m"


class EmbeddingGemmaProvider(EmbeddingProvider):
    def __init__(self, base_url: str, model: str, timeout: float = 60):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = httpx.post(
            f"{self.base_url}/api/embed",
            json={"model": self.model, "input": texts},
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        vectors = payload.get("embeddings") if isinstance(payload, dict) else None
        if not isinstance(vectors, list):
            raise TypeError(f"EmbeddingGemma returned an invalid response: {payload!r}")
        if len(vectors) != len(texts) or any(
            len(vector) != EMBEDDING_DIMENSIONS for vector in vectors
        ):
            raise ValueError(
                "EmbeddingGemma returned vectors with an unexpected count or dimension"
            )
        return [[float(value) for value in vector] for vector in vectors]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]
