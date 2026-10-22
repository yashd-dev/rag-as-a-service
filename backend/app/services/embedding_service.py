import math
import re

import httpx


def validate_vectors(vectors, count, dimensions=768):
    if not isinstance(vectors, list) or len(vectors) != count:
        raise ValueError("Embedding response count mismatch")
    for vector in vectors:
        if (
            not isinstance(vector, list)
            or len(vector) != dimensions
            or any(
                isinstance(v, bool)
                or not isinstance(v, (int, float))
                or not math.isfinite(v)
                for v in vector
            )
            or not any(vector)
        ):
            raise ValueError(
                "Embedding must be finite, nonzero and dimension-compatible"
            )
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
            self.base_url + "/api/embed",
            json={"model": self.model, "input": texts, "truncate": False},
            timeout=120,
        )
        response.raise_for_status()
        return validate_vectors(response.json().get("embeddings"), len(texts))

    def embed_query(self, text):
        return self.embed_texts([text])[0]

    def revision(self):
        response = httpx.get(self.base_url + "/api/tags", timeout=30)
        response.raise_for_status()
        tag = (
            self.model
            if ":" in self.model.rsplit("/", 1)[-1]
            else self.model + ":latest"
        )
        matches = [
            item
            for item in response.json().get("models", [])
            if item.get("name") == tag
        ]
        if len(matches) != 1 or not re.fullmatch(
            r"[0-9a-f]{64}", matches[0].get("digest", "")
        ):
            raise ValueError("Embedding model revision unavailable")
        return {
            "provider": "ollama",
            "model": tag,
            "revision": matches[0]["digest"],
            "dimensions": 768,
        }

    def resolve(self):
        provenance = self.revision()
        self.embed_versioned(["Query model compatibility probe."], provenance)
        return provenance

    def embed_versioned(self, texts, provenance):
        if self.revision() != provenance:
            raise ValueError("Embedding model revision changed")
        vectors = self.embed_texts(texts)
        if self.revision() != provenance:
            raise ValueError("Embedding model revision changed during request")
        return validate_vectors(vectors, len(texts), provenance["dimensions"])


def embedding_provider_for_project(
    config: dict, project: dict
) -> EmbeddingGemmaProvider:
    return EmbeddingGemmaProvider(
        config["OLLAMA_BASE_URL"], config["OLLAMA_EMBEDDING_MODEL"]
    )
