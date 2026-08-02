import faiss
import numpy as np

from config import embedding_model


def create_vector_store(chunks):
    """Create FAISS vector index."""

    embeddings = embedding_model.encode(
        chunks,
        convert_to_numpy=True,
        normalize_embeddings=True
    )

    embeddings = embeddings.astype(np.float32)

    dimension = embeddings.shape[1]

    index = faiss.IndexFlatIP(dimension)

    index.add(embeddings)

    return index


def retrieve_chunks(question, index, chunks, top_k=3):
    """Retrieve top matching chunks."""

    question_embedding = embedding_model.encode(
        [question],
        convert_to_numpy=True,
        normalize_embeddings=True
    )

    question_embedding = question_embedding.astype(np.float32)

    scores, indices = index.search(
        question_embedding,
        top_k
    )

    results = []

    for i in indices[0]:

        if i != -1:
            results.append(chunks[i])

    return results


def retrieve_with_scores(question, index, chunks, top_k=3):
    """Retrieve chunks with similarity scores."""

    question_embedding = embedding_model.encode(
        [question],
        convert_to_numpy=True,
        normalize_embeddings=True
    )

    question_embedding = question_embedding.astype(np.float32)

    scores, indices = index.search(
        question_embedding,
        top_k
    )

    results = []

    for score, idx in zip(scores[0], indices[0]):

        if idx != -1:

            results.append({
                "score": float(score),
                "chunk": chunks[idx]
            })

    return results