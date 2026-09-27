from ai.ingestion.chunker import TextChunker


def test_chunker_overlaps_words():
    text = " ".join(str(index) for index in range(10))
    chunks = TextChunker(chunk_size=4, overlap=1).chunk(text)

    assert [chunk.content for chunk in chunks] == ["0 1 2 3", "3 4 5 6", "6 7 8 9"]
    assert [chunk.chunk_index for chunk in chunks] == [0, 1, 2]


def test_chunker_returns_empty_for_blank_text():
    assert TextChunker().chunk("  \n  ") == []
