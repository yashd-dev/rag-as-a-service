"""Bounded, tenant-scoped visualization reads. Indexing belongs to Stages C/D."""

import json
from html import escape

from neo4j import GraphDatabase


class Neo4jGraphStore:
    def __init__(self, uri, username, password):
        self.driver = GraphDatabase.driver(uri, auth=(username, password))

    def close(self):
        self.driver.close()

    def project_graph(self, project_id, organization_id):
        with self.driver.session(default_access_mode="READ") as session:
            rows = session.execute_read(lambda tx: tx.run(
                "MATCH (n) WHERE n.project_id = $project AND n.organization_id = $org "
                "RETURN n.id AS id, coalesce(n.name, n.file_name, n.id) AS label, labels(n) AS types LIMIT 500",
                project=project_id, org=organization_id,
            ).data())
            ids = [row["id"] for row in rows if row["id"] is not None]
            edges = session.execute_read(lambda tx: tx.run(
                "MATCH (a)-[r]->(b) WHERE a.id IN $ids AND b.id IN $ids "
                "AND a.project_id = $project AND b.project_id = $project "
                "AND a.organization_id = $org AND b.organization_id = $org "
                "RETURN a.id AS source, b.id AS target, type(r) AS type LIMIT 1000",
                ids=ids, project=project_id, org=organization_id,
            ).data())
        return {"nodes": rows, "edges": edges, "bounded": True}

    def project_status(self, project_id, organization_id):
        graph = self.project_graph(project_id, organization_id)
        return {"node_count": len(graph["nodes"]), "edge_count": len(graph["edges"]), "bounded": True,
                "graph_ready": False, "reason": "retrieval_not_verified"}


def render_graph_html(graph):
    # shortcut: accessible static evidence listing, restore interactive layout only when needed for source navigation.
    return '<!doctype html><html lang="en"><meta charset="utf-8"><title>Project graph</title><body><h1>Project graph</h1><pre>' + escape(json.dumps(graph, indent=2, ensure_ascii=False)) + '</pre></body></html>'
