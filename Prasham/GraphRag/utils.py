import re
import json
from urllib.request import urlopen

import fitz


DATASET_URL = "https://rag-as-a-service-production.up.railway.app/contents?limit=5&offset=0&include_pending=false"


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


def load_dataset(url=DATASET_URL):
    """Load first 5 OCR documents from the dataset API."""

    with urlopen(url, timeout=60) as response:
        data = json.load(response)

    chunks = []

    for item in data.get("items", []):
        if item.get("ocr_status") != "done" or not item.get("ocr_text"):
            continue

        source = item.get("path") or item.get("url") or "unknown source"
        text = clean_text(item["ocr_text"])

        for chunk in chunk_text(text):
            chunks.append(f"Source: {source}\n\n{chunk}")

    return chunks
