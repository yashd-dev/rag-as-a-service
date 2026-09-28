from ai.ingestion.chunker import TextChunker, clean_ocr_for_graph


def test_chunker_overlaps_words():
    text = " ".join(str(index) for index in range(10))
    chunks = TextChunker(chunk_size=4, overlap=1).chunk(text)

    assert [chunk.content for chunk in chunks] == ["0 1 2 3", "3 4 5 6", "6 7 8 9"]
    assert [chunk.chunk_index for chunk in chunks] == [0, 1, 2]


def test_chunker_returns_empty_for_blank_text():
    assert TextChunker().chunk("  \n  ") == []


def test_clean_ocr_for_graph_removes_report_noise():
    text = """
222
A
SUPREME COURT REPORTS
[1973] 3 S.C.R.
T. GOVINDARAJA MUDALIAR ETC. ETC. v. THE STATE OF TAMIL NADU & OTHERS
Constitution of India, Article 19(1)(f)-Motor Vehicle Act 1939
16-631Sup. CI/73
GOVINDARAJA v. TAMIL NADU (Grover, J.)
"""

    cleaned = clean_ocr_for_graph(text)

    assert "222" not in cleaned
    assert "SUPREME COURT REPORTS" not in cleaned
    assert "[1973] 3 S.C.R." not in cleaned
    assert "16-631Sup. CI/73" not in cleaned
    assert "T. GOVINDARAJA MUDALIAR" in cleaned
    assert "Constitution of India" in cleaned


def test_clean_ocr_for_graph_joins_hyphenated_words():
    cleaned = clean_ocr_for_graph("nationalisa-\n tion of State Carriage")

    assert "nationalisation" in cleaned
