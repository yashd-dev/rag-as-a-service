import os
from dotenv import load_dotenv

from config import client, LLM_MODEL
from utils import load_document
from graph import build_graph, get_graph_context
from rag import create_vector_store, retrieve_chunks

load_dotenv()


def run_graphrag(pdf_path, question, top_k=3):
    chunks = load_document(pdf_path)
    graph = build_graph(chunks)
    index = create_vector_store(chunks)

    relevant_chunks = retrieve_chunks(question, index, chunks, top_k)
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

    response = client.models.generate_content(
        model=LLM_MODEL,
        contents=prompt
    )

    return {
        "answer": response.text,
        "sources": relevant_chunks,
        "graph_context": graph_context
    }


def main():
    pdf_path = "data/sample_case.pdf"

    if not os.path.exists(pdf_path):
        print(f"Error: {pdf_path} not found.")
        return

    chunks = load_document(pdf_path)
    graph = build_graph(chunks)
    index = create_vector_store(chunks)

    print("Legal GraphRAG ready.\n")

    while True:
        question = input("\nQuestion: ").strip()

        if question.lower() in ["quit", "exit", "q"]:
            break

        if not question:
            continue

        relevant_chunks = retrieve_chunks(question, index, chunks, top_k=3)
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

        response = client.models.generate_content(
            model=LLM_MODEL,
            contents=prompt
        )

        print("\n" + "=" * 80)
        print(response.text)
        print("=" * 80)

        print("\nSources:")
        for i, chunk in enumerate(relevant_chunks, 1):
            print(f"\n[{i}] {chunk[:200]}...")

        if graph_context:
            print(f"\nGraph Context:\n{graph_context}")


if __name__ == "__main__":
    main()