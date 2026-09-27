from neo4j import GraphDatabase


class Neo4jGraphStore:
    def __init__(self, uri: str, username: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(username, password))

    def close(self) -> None:
        self.driver.close()

    def ensure_constraints(self) -> None:
        statements = [
            "CREATE CONSTRAINT organization_id IF NOT EXISTS FOR (o:Organization) REQUIRE o.id IS UNIQUE",
            "CREATE CONSTRAINT project_id IF NOT EXISTS FOR (p:Project) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT document_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
            "CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE",
            "CREATE INDEX entity_project_name IF NOT EXISTS FOR (e:Entity) ON (e.project_id, e.normalized_name)",
        ]
        with self.driver.session() as session:
            for statement in statements:
                session.run(statement)

    def project_exists(self, project_id: str, organization_id: str) -> bool:
        query = """
        MATCH (p:Project {id: $project_id, organization_id: $organization_id})
        RETURN count(p) > 0 AS exists
        """
        with self.driver.session() as session:
            row = session.run(query, project_id=project_id, organization_id=organization_id).single()
        return bool(row and row["exists"])

    def project_status(self, project_id: str, organization_id: str) -> dict:
        if not self.project_exists(project_id, organization_id):
            return {"exists": False, "node_count": 0, "edge_count": 0}
        node_query = """
        MATCH (e:Entity {project_id: $project_id, organization_id: $organization_id})
        RETURN count(e) AS node_count
        """
        edge_query = """
        MATCH (:Entity {project_id: $project_id, organization_id: $organization_id})-[r:RELATES_TO]-(:Entity {project_id: $project_id, organization_id: $organization_id})
        RETURN count(DISTINCT r) AS edge_count
        """
        with self.driver.session() as session:
            node_row = session.run(node_query, project_id=project_id, organization_id=organization_id).single()
            edge_row = session.run(edge_query, project_id=project_id, organization_id=organization_id).single()
        return {
            "exists": True,
            "node_count": node_row["node_count"] if node_row else 0,
            "edge_count": edge_row["edge_count"] if edge_row else 0,
        }

    def project_graph(self, project_id: str, organization_id: str, limit: int = 500) -> dict:
        if not self.project_exists(project_id, organization_id):
            return {"nodes": [], "edges": []}
        query = """
        MATCH (e:Entity {project_id: $project_id, organization_id: $organization_id})
        OPTIONAL MATCH (e)-[r:RELATES_TO]-(n:Entity {project_id: $project_id, organization_id: $organization_id})
        RETURN e.id AS source_id, e.name AS source_name, n.id AS target_id, n.name AS target_name, r.relation AS relation
        LIMIT $limit
        """
        nodes = {}
        edges = []
        with self.driver.session() as session:
            rows = session.run(query, project_id=project_id, organization_id=organization_id, limit=limit)
            for row in rows:
                nodes[row["source_id"]] = row["source_name"]
                if row["target_id"]:
                    nodes[row["target_id"]] = row["target_name"]
                    edges.append({"source": row["source_id"], "target": row["target_id"], "label": row["relation"]})
        return {"nodes": [{"id": node_id, "label": label} for node_id, label in nodes.items()], "edges": edges}
