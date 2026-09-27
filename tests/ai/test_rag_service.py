from ai.llm.base import LLMProvider
from ai.rag.service import RagService
from ai.schemas.retrieval import RetrievedChunk


class FakeLLM(LLMProvider):
    def generate(self, prompt: str) -> str:
        assert "Question: What?" in prompt
        assert "[chunk_1] Context" in prompt
        return "Answer"


def test_rag_service_builds_grounded_prompt():
    result = RagService(FakeLLM()).answer("What?", [RetrievedChunk("chunk_1", "doc_1", "Context")])

    assert result == {"answer": "Answer", "sources": ["chunk_1"]}
