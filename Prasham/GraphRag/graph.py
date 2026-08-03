import json
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx

from config import generate_text


ALLOWED_RELATIONS = [
    "cites",
    "refers_to",
    "interprets",
    "applies",
    "mentions",
    "decides",
    "protects",
    "defines"
]


def normalize_text(text):
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def question_mentions_entity(question, entity):
    question = normalize_text(question)
    entity = normalize_text(entity)

    if not entity:
        return False

    if entity in question:
        return True

    entity_words = [word for word in entity.split() if len(word) > 2]

    return len(entity_words) > 1 and all(word in question for word in entity_words)


def extract_graph(chunk):
    """Extract entities and relationships using the configured LLM."""

    prompt = f"""
You are a legal knowledge graph extractor.

Extract ONLY the important legal entities and relationships.

Allowed relationship labels:
{", ".join(ALLOWED_RELATIONS)}

Return ONLY valid JSON.

Format:

{{
  "entities":[
      "Entity 1",
      "Entity 2"
  ],

  "relationships":[
      {{
          "source":"Entity 1",
          "target":"Entity 2",
          "relation":"mentions"
      }}
  ]
}}

Rules:
- No explanation.
- No markdown.
- No ```json.
- Use only the allowed relationship labels.

Text:

{chunk}
"""

    text = generate_text(prompt).strip()

    text = re.sub(r"^```json", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^```", "", text)
    text = re.sub(r"```$", "", text)
    text = text.strip()

    try:
        return json.loads(text)

    except Exception:

        return {
            "entities": [],
            "relationships": []
        }


def build_graph(chunks, verbose=False):
    """Build NetworkX graph."""

    graph = nx.DiGraph()

    for chunk_index, chunk in enumerate(chunks):
        chunk_number = chunk_index + 1
        if verbose:
            print(f"Graph: extracting chunk {chunk_number}/{len(chunks)}")

        data = extract_graph(chunk)

        entities = data.get("entities", [])

        relationships = data.get("relationships", [])

        if verbose:
            print(f"Graph: found {len(entities)} entities, {len(relationships)} relationships")

        for entity in entities:
            if verbose and entity not in graph:
                print(f"  entity: {entity}")

            graph.add_node(entity)
            graph.nodes[entity].setdefault("chunks", [])

            if chunk_index not in graph.nodes[entity]["chunks"]:
                graph.nodes[entity]["chunks"].append(chunk_index)

        for relation in relationships:

            source = relation.get("source")
            target = relation.get("target")
            label = relation.get("relation")

            if not source or not target:
                continue

            if label not in ALLOWED_RELATIONS:
                label = "mentions"

            if verbose:
                print(f"  edge: {source} --{label}--> {target}")

            for entity in [source, target]:
                graph.add_node(entity)
                graph.nodes[entity].setdefault("chunks", [])

                if chunk_index not in graph.nodes[entity]["chunks"]:
                    graph.nodes[entity]["chunks"].append(chunk_index)

            graph.add_edge(
                source,
                target,
                relation=label
            )

    return graph


def retrieve_graph_chunks(question, graph, chunks, limit=3):
    """Retrieve chunks linked to graph entities in the question."""

    matched_entities = [
        node for node in graph.nodes()
        if question_mentions_entity(question, node)
    ]

    related_entities = set(matched_entities)

    for entity in matched_entities:
        related_entities.update(graph.neighbors(entity))
        related_entities.update(graph.predecessors(entity))

    chunk_indices = []

    for entity in related_entities:
        chunk_indices.extend(graph.nodes[entity].get("chunks", []))

    results = []

    for chunk_index in chunk_indices:
        if chunk_index < len(chunks) and chunks[chunk_index] not in results:
            results.append(chunks[chunk_index])

        if len(results) == limit:
            break

    return results


def save_graph(graph, output_dir="outputs"):
    """Save graph data and a quick PNG plot."""

    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    json_path = output_path / "graph.json"
    png_path = output_path / "graph.png"

    data = {
        "nodes": [
            {
                "id": node,
                "chunks": values.get("chunks", [])
            }
            for node, values in graph.nodes(data=True)
        ],
        "edges": [
            {
                "source": source,
                "target": target,
                "relation": values.get("relation", "mentions")
            }
            for source, target, values in graph.edges(data=True)
        ]
    }

    with json_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)

    plt.figure(figsize=(18, 12))
    pos = nx.spring_layout(graph, seed=42, k=0.8)
    nx.draw(
        graph,
        pos,
        with_labels=True,
        node_size=900,
        font_size=7,
        arrows=True
    )
    nx.draw_networkx_edge_labels(
        graph,
        pos,
        edge_labels=nx.get_edge_attributes(graph, "relation"),
        font_size=6
    )
    plt.tight_layout()
    plt.savefig(png_path, dpi=200)
    plt.close()

    return json_path, png_path


def load_graph(path="outputs/graph.json"):
    with Path(path).open(encoding="utf-8") as file:
        data = json.load(file)

    graph = nx.DiGraph()

    for node in data.get("nodes", []):
        if isinstance(node, str):
            graph.add_node(node, chunks=[])
        else:
            graph.add_node(node["id"], chunks=node.get("chunks", []))

    for edge in data.get("edges", []):
        graph.add_edge(
            edge["source"],
            edge["target"],
            relation=edge.get("relation", "mentions")
        )

    return graph


def get_graph_context(question, graph):
    """Retrieve graph facts related to the question."""

    context = []

    visited = set()

    for node in graph.nodes():

        if question_mentions_entity(question, node):

            if node not in visited:

                visited.add(node)

                context.append(f"Entity: {node}")

            for neighbor in graph.neighbors(node):

                relation = graph[node][neighbor]["relation"]

                context.append(
                    f"{node} --{relation}--> {neighbor}"
                )

    return "\n".join(context)
