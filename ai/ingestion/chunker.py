import re

from ai.schemas.documents import TextChunk


def count_tokens(text: str) -> int:
    return len(text.split())


class TextChunker:
    def __init__(self, chunk_size: int = 1000, overlap: int = 120):
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if overlap < 0 or overlap >= chunk_size:
            raise ValueError("overlap must be non-negative and smaller than chunk_size")
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text: str) -> list[TextChunk]:
        words = re.findall(r"\S+", text)
        if not words:
            return []

        chunks = []
        start = 0
        while start < len(words):
            end = min(start + self.chunk_size, len(words))
            content = " ".join(words[start:end])
            chunks.append(TextChunk(len(chunks), content, end - start))
            if end == len(words):
                break
            start = end - self.overlap
        return chunks
