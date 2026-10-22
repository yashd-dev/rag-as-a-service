"""Read-transaction Neo4j schema discovery; unknown topology stays unknown."""


def graph_report(uri, username, password, org, project):
    from neo4j import READ_ACCESS, GraphDatabase, unit_of_work

    queries = {
        "server": "CALL dbms.components() YIELD name, versions, edition RETURN name, versions, edition",
        "indexes": "SHOW INDEXES YIELD * RETURN *",
        "constraints": "SHOW CONSTRAINTS YIELD * RETURN *",
        "labels": "MATCH (n) WHERE n.organization_id = $org AND n.project_id = $project "
        "UNWIND labels(n) AS label RETURN label, count(*) AS count ORDER BY label",
        "properties": "MATCH (n) WHERE n.organization_id = $org AND n.project_id = $project "
        "UNWIND keys(n) AS property RETURN property, count(*) AS count ORDER BY property",
        "relationships": "MATCH (a)-[r]->(b) WHERE a.organization_id = $org AND a.project_id = $project "
        "RETURN type(r) AS type, count(*) AS count, "
        "sum(CASE WHEN b.organization_id = $org AND b.project_id = $project "
        "THEN 0 ELSE 1 END) AS foreign_or_unscoped_endpoints ORDER BY type",
        "duplicate_ids": "MATCH (n) WHERE n.organization_id = $org AND n.project_id = $project "
        "AND n.id IS NOT NULL WITH n.id AS id, count(*) AS copies "
        "WHERE copies > 1 RETURN count(*) AS duplicate_id_groups",
        "scope_property_coverage": "MATCH (n) RETURN count(*) AS database_nodes, "
        "count(n.organization_id) AS with_organization_id, "
        "count(n.project_id) AS with_project_id",
    }
    result = {
        "queries": queries,
        "measurements": {},
        "blockers": [
            (
                "Scope property names organization_id/project_id are candidates from the application contract; "
                "zero matches do not prove an empty graph until deployed graph scope mapping is reviewed."
            ),
            (
                "Chunk/entity/assertion roles, vector properties and evidence topology require review of discovered schema; "
                "semantic provenance coverage, missing/stale vectors and dangling source references remain unknown."
            ),
        ],
    }
    with (
        GraphDatabase.driver(
            uri,
            auth=(username, password),
            connection_timeout=10,
            connection_acquisition_timeout=15,
            max_transaction_retry_time=0,
        ) as driver,
        driver.session(default_access_mode=READ_ACCESS) as session,
    ):
        for name, query in queries.items():
            try:
                # Explicit, time-bounded read transactions; never ensure/create anything.
                result["measurements"][name] = session.execute_read(
                    unit_of_work(timeout=30)(
                        lambda tx, q=query: [
                            dict(row) for row in tx.run(q, org=org, project=project)
                        ]
                    )
                )
            except Exception as exc:  # noqa: BLE001 - redact all driver error messages
                result["measurements"][name] = {
                    "state": "blocked",
                    "error_type": type(exc).__name__,
                }
    return result
