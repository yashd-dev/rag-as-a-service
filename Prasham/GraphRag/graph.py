import json
import re
import networkx as nx

from config import client, LLM_MODEL


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


def extract_graph(chunk):
    """Extract entities and relationships using Gemini."""

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

    response = client.models.generate_content(
        model=LLM_MODEL,
        contents=prompt
    )

    text = response.text.strip()

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


def build_graph(chunks):
    """Build NetworkX graph."""

    graph = nx.DiGraph()

    for chunk in chunks:

        data = extract_graph(chunk)

        entities = data.get("entities", [])

        relationships = data.get("relationships", [])

        for entity in entities:

            graph.add_node(entity)

        for relation in relationships:

            source = relation.get("source")
            target = relation.get("target")
            label = relation.get("relation")

            if not source or not target:
                continue

            if label not in ALLOWED_RELATIONS:
                label = "mentions"

            graph.add_edge(
                source,
                target,
                relation=label
            )

    return graph


def get_graph_context(question, graph):
    """Retrieve graph facts related to the question."""

    question = question.lower()

    context = []

    visited = set()

    for node in graph.nodes():

        if node.lower() in question:

            if node not in visited:

                visited.add(node)

                context.append(f"Entity: {node}")

            for neighbor in graph.neighbors(node):

                relation = graph[node][neighbor]["relation"]

                context.append(
                    f"{node} --{relation}--> {neighbor}"
                )

    return "\n".join(context)