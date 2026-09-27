from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    document_id: str
    content: str
    score: float | None = None
    file_name: str | None = None
    page_number: int | None = None
