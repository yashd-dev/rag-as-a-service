import json
import os
from pathlib import Path

from dotenv import load_dotenv

from config import generate_text
from utils import DATASET_URL, load_dataset, load_document
from graph import build_graph, get_graph_context, load_graph, retrieve_graph_chunks, save_graph
from rag import create_vector_store, load_vector_store, retrieve_chunks, save_vector_store

load_dotenv()

CACHE_DIR = Path("outputs")
CHUNKS_PATH = CACHE_DIR / "chunks.json"
GRAPH_PATH = CACHE_DIR / "graph.json"
INDEX_PATH = CACHE_DIR / "faiss.index"


def merge_chunks(*chunk_groups):
    merged = []

    for chunk_group in chunk_groups:
        for chunk in chunk_group:
            if chunk not in merged:
                merged.append(chunk)

    return merged


def read_question():
    print("\nQuestion (blank line to submit, q to quit):")
    lines = []

    while True:
        line = input().strip()

        if not lines and line.lower() in ["quit", "exit", "q"]:
            return line

        if not line:
            return "\n".join(lines).strip()

        lines.append(line)


def load_or_build_index(dataset_url):
    if CHUNKS_PATH.exists() and GRAPH_PATH.exists() and INDEX_PATH.exists():
        print("Loading cached chunks, graph, and vector index...")

        with CHUNKS_PATH.open(encoding="utf-8") as file:
            chunks = json.load(file)

        graph = load_graph(GRAPH_PATH)

        if any(values.get("chunks") for _, values in graph.nodes(data=True)):
            return chunks, graph, load_vector_store(str(INDEX_PATH))

        print("Cached graph has no chunk links. Rebuilding cache...")

    chunks = load_dataset(dataset_url)

    if not chunks:
        return [], None, None

    CACHE_DIR.mkdir(exist_ok=True)

    print(f"Loaded {len(chunks)} chunks from dataset. Building graph...")
    graph = build_graph(chunks, verbose=True)
    graph_json, graph_png = save_graph(graph, CACHE_DIR)
    print(f"Saved graph JSON: {graph_json}")
    print(f"Saved graph plot: {graph_png}")

    print("Building vector index...")
    index = create_vector_store(chunks)
    save_vector_store(index, str(INDEX_PATH))

    with CHUNKS_PATH.open("w", encoding="utf-8") as file:
        json.dump(chunks, file, ensure_ascii=False, indent=2)

    print(f"Saved chunks: {CHUNKS_PATH}")
    print(f"Saved vector index: {INDEX_PATH}")

    return chunks, graph, index


def run_graphrag(pdf_path, question, top_k=3):
    chunks = load_document(pdf_path)
    graph = build_graph(chunks)
    index = create_vector_store(chunks)

    vector_chunks = retrieve_chunks(question, index, chunks, top_k)
    graph_chunks = retrieve_graph_chunks(question, graph, chunks, top_k)
    relevant_chunks = merge_chunks(vector_chunks, graph_chunks)
    graph_context = get_graph_context(question, graph)

    combined_chunks = "\n\n---\n\n".join(relevant_chunks)

    prompt = f"""
You are a legal expert assistant. Answer the question based on the provided context.

Context from relevant document sections:

{combined_chunks}

Knowledge Graph Relationships:

{graph_context if graph_context else "No direct entity matches found in the knowledge graph."}

Question: {question}

Instructions:
- Base your answer on the provided context.
- If the context is insufficient, say so.
- Be precise and concise.
- Cite specific sources when possible.
"""

    return {
        "answer": generate_text(prompt),
        "sources": relevant_chunks,
        "graph_context": graph_context
    }


def main():
    dataset_url = os.getenv("DATASET_URL", DATASET_URL)
    chunks, graph, index = load_or_build_index(dataset_url)

    if not chunks:
        print("Error: no OCR text found in dataset.")
        return

    print("Legal GraphRAG ready.\n")

    while True:
        question = read_question()

        if question.lower() in ["quit", "exit", "q"]:
            break

        if not question:
            continue

        vector_chunks = retrieve_chunks(question, index, chunks, top_k=3)
        graph_chunks = retrieve_graph_chunks(question, graph, chunks, limit=3)
        relevant_chunks = merge_chunks(vector_chunks, graph_chunks)
        graph_context = get_graph_context(question, graph)

        print(f"Retrieved {len(vector_chunks)} vector chunks + {len(graph_chunks)} graph chunks.")

        combined_chunks = "\n\n---\n\n".join(relevant_chunks)

        prompt = f"""
You are a legal expert assistant. Answer the question based on the provided context.

Context from relevant document sections:

{combined_chunks}

Knowledge Graph Relationships:

{graph_context if graph_context else "No direct entity matches found in the knowledge graph."}

Question: {question}

Instructions:
- Base your answer on the provided context.
- If the context is insufficient, say so.
- Be precise and concise.
- Cite specific sources when possible.
"""

        print("\n" + "=" * 80)
        print(generate_text(prompt))
        print("=" * 80)

        print("\nSources:")
        for i, chunk in enumerate(relevant_chunks, 1):
            print(f"\n[{i}] {chunk[:200]}...")

        if graph_context:
            print(f"\nGraph Context:\n{graph_context}")


if __name__ == "__main__":
    main()
