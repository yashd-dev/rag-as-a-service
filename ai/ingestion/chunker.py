import re

from ai.schemas.documents import TextChunk


def count_tokens(text: str) -> int:
    return len(text.split())


def clean_ocr_for_graph(text: str) -> str:
    """Remove OCR/report noise before graph extraction while preserving legal facts."""
    text = re.sub(r"([A-Za-z])-\s*\n\s*([a-z])", r"\1\2", text)
    kept_lines = []
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        if re.fullmatch(r"\d{1,4}", line):
            continue
        if re.fullmatch(r"[A-H]", line):
            continue
        normalized = line.lower().strip(" .:-")
        if normalized in {
            "supreme court reports",
            "appeals dismissed",
        }:
            continue
        if re.fullmatch(r"\[\d{4}\]\s+\d+\s+s\.c\.r\.?", line, flags=re.IGNORECASE):
            continue
        if re.fullmatch(r"\d+-\d+sup\.\s*ci/\d+", line, flags=re.IGNORECASE):
            continue
        kept_lines.append(line)

    cleaned = "\n".join(kept_lines)
    cleaned = re.sub(r"([A-Za-z])-\s+([a-z])", r"\1\2", cleaned)
    cleaned = re.sub(r"\s+([,.;:)\]])", r"\1", cleaned)
    cleaned = re.sub(r"([(\[])\s+", r"\1", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


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
