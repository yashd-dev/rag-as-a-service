from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    chunk_index: int
    content: str
    token_count: int
    page_number: int | None = None
    section_title: str | None = None


@dataclass(frozen=True)
class SourceObject:
    object_key: str
    size_bytes: int | None = None
    etag: str | None = None
    last_modified: str | None = None
    content_type: str | None = None
    url: str | None = None
