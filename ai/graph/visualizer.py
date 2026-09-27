from html import escape


def render_graph_html(graph: dict) -> str:
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    node_items = "".join(f"<li>{escape(node['label'])}</li>" for node in nodes)
    edge_items = "".join(f"<li>{escape(edge['source'])} -> {escape(edge['target'])}: {escape(str(edge.get('label') or 'related'))}</li>" for edge in edges)
    return f"""
<!doctype html>
<html>
  <head><meta charset="utf-8"><title>Project graph</title></head>
  <body style="font-family:Inter,system-ui,sans-serif;background:#0b0b0f;color:#f5f5f5;padding:24px;">
    <h1>Knowledge Graph</h1>
    <p>{len(nodes)} nodes · {len(edges)} edges</p>
    <h2>Entities</h2>
    <ul>{node_items or '<li>No graph entities indexed yet.</li>'}</ul>
    <h2>Relationships</h2>
    <ul>{edge_items or '<li>No relationships indexed yet.</li>'}</ul>
  </body>
</html>
""".strip()
