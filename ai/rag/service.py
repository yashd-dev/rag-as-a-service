from ai.llm.base import LLMProvider
from ai.rag.generator import build_grounded_prompt
from ai.schemas.retrieval import RetrievedChunk


class RagService:
    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def answer(self, query: str, chunks: list[RetrievedChunk]) -> dict:
        prompt = build_grounded_prompt(query, chunks)
        return {"answer": self.llm.generate(prompt), "sources": [chunk.chunk_id for chunk in chunks]}
