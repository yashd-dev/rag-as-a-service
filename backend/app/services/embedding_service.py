from ai.embeddings.embeddinggemma import EmbeddingGemmaProvider


def embedding_provider_for_project(
    config: dict, project: dict
) -> EmbeddingGemmaProvider:
    return EmbeddingGemmaProvider(
        config["OLLAMA_BASE_URL"], config["OLLAMA_EMBEDDING_MODEL"]
    )
