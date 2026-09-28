from neo4j import GraphDatabase

from ai.graph.extractor import entity_id, normalize_entity_name


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
        MATCH (p:Project {id: $project_id})
        WHERE p.organization_id = $organization_id
        RETURN count(p) > 0 AS exists
        """
        with self.driver.session() as session:
            row = session.run(query, project_id=project_id, organization_id=organization_id).single()
        return bool(row and row["exists"])

    def ensure_project(self, project: dict) -> None:
        query = """
        MERGE (o:Organization {id: $organization_id})
        MERGE (p:Project {id: $project_id})
        SET p.organization_id = $organization_id,
            p.name = $project_name,
            p.slug = $project_slug
        MERGE (o)-[:OWNS]->(p)
        """
        with self.driver.session() as session:
            session.run(
                query,
                organization_id=project["organization_id"],
                project_id=project["id"],
                project_name=project["name"],
                project_slug=project["slug"],
            )

    def ingest_document(self, project: dict, document: dict, chunks: list, entities: list, relations: list) -> None:
        self.ensure_project(project)
        entity_lookup = {entity.normalized_name: entity for entity in entities}
        query = """
        MATCH (p:Project {id: $project_id})
        MERGE (d:Document {id: $document_id})
        SET d.project_id = $project_id,
            d.organization_id = $organization_id,
            d.file_name = $file_name
        MERGE (p)-[:HAS_DOCUMENT]->(d)
        WITH d
        UNWIND $chunks AS chunk
        MERGE (c:Chunk {id: chunk.id})
        SET c.project_id = $project_id,
            c.organization_id = $organization_id,
            c.document_id = $document_id,
            c.content = chunk.content,
            c.token_count = chunk.token_count,
            c.index = chunk.index
        MERGE (d)-[:HAS_CHUNK]->(c)
        """
        entity_query = """
        MATCH (d:Document {id: $document_id})
        UNWIND $entities AS entity
        MERGE (e:Entity {id: entity.id})
        SET e.project_id = $project_id,
            e.organization_id = $organization_id,
            e.name = entity.name,
            e.normalized_name = entity.normalized_name,
            e.type = entity.type,
            e.description = entity.description
        MERGE (d)-[:MENTIONS]->(e)
        """
        relation_query = """
        UNWIND $relations AS relation
        MATCH (source:Entity {id: relation.source_id})
        MATCH (target:Entity {id: relation.target_id})
        MERGE (source)-[r:RELATES_TO {relation: relation.relation}]->(target)
        SET r.project_id = $project_id,
            r.organization_id = $organization_id,
            r.description = relation.description,
            r.weight = relation.weight
        """
        chunk_rows = [
            {
                "id": f"chunk:{document['id']}:{chunk.chunk_index}",
                "index": chunk.chunk_index,
                "content": chunk.content,
                "token_count": chunk.token_count,
            }
            for chunk in chunks
        ]
        entity_rows = [
            {
                "id": entity_id(project["id"], entity.normalized_name),
                "name": entity.name,
                "normalized_name": entity.normalized_name,
                "type": entity.entity_type,
                "description": entity.description,
            }
            for entity in entities
        ]
        relation_rows = []
        for relation in relations:
            source = entity_lookup.get(normalize_entity_name(relation.source))
            target = entity_lookup.get(normalize_entity_name(relation.target))
            if source and target:
                relation_rows.append(
                    {
                        "source_id": entity_id(project["id"], source.normalized_name),
                        "target_id": entity_id(project["id"], target.normalized_name),
                        "relation": relation.relation,
                        "description": relation.description,
                        "weight": relation.weight,
                    }
                )
        params = {
            "project_id": project["id"],
            "organization_id": project["organization_id"],
            "document_id": document["id"],
            "file_name": document["file_name"],
        }
        with self.driver.session() as session:
            session.run(query, **params, chunks=chunk_rows)
            if entity_rows:
                session.run(entity_query, **params, entities=entity_rows)
            if relation_rows:
                session.run(relation_query, **params, relations=relation_rows)

    def project_status(self, project_id: str, organization_id: str) -> dict:
        node_query = """
        MATCH (e:Entity {project_id: $project_id, organization_id: $organization_id})
        RETURN count(e) AS node_count
        """
        with self.driver.session() as session:
            node_row = session.run(node_query, project_id=project_id, organization_id=organization_id).single()
            edge_count = self.relation_count(session, project_id, organization_id)
        return {
            "exists": True,
            "node_count": node_row["node_count"] if node_row else 0,
            "edge_count": edge_count,
        }

    def project_graph(self, project_id: str, organization_id: str, limit: int = 500) -> dict:
        node_query = """
        MATCH (e:Entity {project_id: $project_id, organization_id: $organization_id})
        RETURN e.id AS id, e.name AS name
        LIMIT $limit
        """
        edge_query = """
        MATCH (e:Entity {project_id: $project_id, organization_id: $organization_id})-[r]-(n:Entity {project_id: $project_id, organization_id: $organization_id})
        WHERE type(r) = 'RELATES_TO'
        RETURN e.id AS source_id, n.id AS target_id, r.relation AS relation
        LIMIT $limit
        """
        nodes = {}
        edges = []
        with self.driver.session() as session:
            for row in session.run(node_query, project_id=project_id, organization_id=organization_id, limit=limit):
                nodes[row["id"]] = row["name"]
            if self.relation_count(session, project_id, organization_id):
                for row in session.run(edge_query, project_id=project_id, organization_id=organization_id, limit=limit):
                    edges.append({"source": row["source_id"], "target": row["target_id"], "label": row["relation"]})
        return {"nodes": [{"id": node_id, "label": label} for node_id, label in nodes.items()], "edges": edges}

    def relation_count(self, session, project_id: str, organization_id: str) -> int:
        query = """
        MATCH (:Entity {project_id: $project_id, organization_id: $organization_id})-[r]-(:Entity {project_id: $project_id, organization_id: $organization_id})
        WHERE type(r) = 'RELATES_TO'
        RETURN count(DISTINCT r) AS edge_count
        """
        row = session.run(query, project_id=project_id, organization_id=organization_id).single()
        return row["edge_count"] if row else 0
