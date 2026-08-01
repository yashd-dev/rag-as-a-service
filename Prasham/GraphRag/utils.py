import re
import fitz


def extract_text(pdf_path):
    """Extract text from PDF."""

    document = fitz.open(pdf_path)
    pages = []

    for page in document:
        pages.append(page.get_text())

    document.close()

    return "\n".join(pages)


def clean_text(text):
    """Clean extracted text."""

    text = text.replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\n+", "\n", text)

    return text.strip()


def chunk_text(text, chunk_size=800, overlap=150):
    """Create overlapping chunks."""

    words = text.split()

    chunks = []

    start = 0

    while start < len(words):

        end = start + chunk_size

        chunk = " ".join(words[start:end])

        chunks.append(chunk)

        start += chunk_size - overlap

    return chunks


def load_document(pdf_path):
    """Complete preprocessing."""

    text = extract_text(pdf_path)

    text = clean_text(text)

    chunks = chunk_text(text)

    return chunks
