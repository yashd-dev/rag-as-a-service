from ai.schemas.retrieval import RetrievedChunk


def build_grounded_prompt(query: str, chunks: list[RetrievedChunk]) -> str:
    context = "\n\n".join(f"[{chunk.chunk_id}] {chunk.content}" for chunk in chunks)
    return (
        "Use only the provided context when possible. "
        "If context is insufficient, say what is missing.\n\n"
        f"Context:\n{context}\n\nQuestion: {query}"
    )
