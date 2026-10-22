"""Extractor-versioned graph evidence anchored to existing Neo4j vector chunks."""

import json
import logging
from collections import Counter

from neo4j import unit_of_work

from backend.app.db.repository import now_ms
from backend.app.services.graph_extraction import (
    ENTITY_TYPES,
    ExtractionError,
    validate_extraction,
)
from backend.app.services.rag import fingerprint


class EvidenceGraph:
    def __init__(self, vectors, profile):
        self.vectors, self.profile = vectors, profile
        self.key = fingerprint([vectors.key, profile])
        self.scope = {
            "graph_key": self.key,
            "vector_partition": vectors.key,
            "organization_id": vectors.snapshot["organization_id"],
            "project_id": vectors.snapshot["project_id"],
        }
        self.rows = {row["id"]: row for row in vectors.snapshot["rows"]}

    def prepare(self):
        for label in (
            "RAGEndpoint",
            "RAGAssertion",
            "RAGEvidence",
            "RAGExtraction",
            "RAGGraphPublication",
        ):
            self.vectors._run(
                f"CREATE CONSTRAINT {label.lower()}_key IF NOT EXISTS FOR (n:{label}) REQUIRE n.key IS UNIQUE",
                write=True,
            )

    def document(self, row):
        return self.scope | {
            "key": fingerprint([self.key, "document", row["document_id"]]),
            "id": row["document_id"],
            "document_id": row["document_id"],
            "generation_id": row["generation_id"],
        }

    def evidence(self, row, result):
        records = {}
        for kind, objects, field in (
            ("mention", result["entities"], "mentions"),
            ("assertion", result["assertions"], "evidence"),
        ):
            for item in objects:
                for span in item[field]:
                    key = fingerprint([self.key, kind, item["key"], span])
                    records[key] = (
                        self.scope
                        | span
                        | {
                            "key": key,
                            "id": key,
                            "kind": kind,
                            "target_key": item["key"],
                            "content_hash": row["content_hash"],
                            "method": result["method"],
                        }
                    )
        return records

    def cached(self):
        records = self.vectors._run(
            "MATCH (x:RAGExtraction {graph_key:$graph}) OPTIONAL MATCH (x)-[:FROM_CHUNK]->(c) "
            "RETURN properties(x) AS extraction,collect(c.key) AS chunks",
            graph=self.key,
        )
        result = {
            record["extraction"]["chunk_id"]: record["extraction"]
            | {"chunk_keys": record["chunks"]}
            for record in records
        }
        if len(result) != len(records):
            raise ValueError("Duplicate extraction records")
        return result

    def cached_result(self, row, record, require_success=True):
        if (
            (require_success and record.get("state") not in {"extracted", "empty"})
            or record.get("content_hash") != row["content_hash"]
            or record.get("key") != fingerprint([self.key, row["id"]])
            or any(record.get(k) != v for k, v in self.scope.items())
            or record.get("chunk_keys") != [self.vectors.properties(row)["key"]]
            or record.get("profile_json") != json.dumps(self.profile, sort_keys=True)
        ):
            return None
        try:
            result = validate_extraction(
                json.loads(record["result_json"]), row, self.key
            )
            if record.get("state") in {"extracted", "empty"} and (
                record["state"] == "empty"
            ) != (not result["entities"]):
                return None
            return result if fingerprint(result) == record.get("result_hash") else None
        except (ValueError, KeyError, TypeError):
            return None

    def attempt(self, row, error=None):
        self.vectors._run(
            "MERGE (x:RAGExtraction {key:$key}) SET x += $scope, x.chunk_id=$chunk, x.content_hash=$hash, "
            "x.profile_json=$profile, x.state=$state, x.error_code=$error, x.updated_at=$timestamp "
            "SET x.attempts=coalesce(x.attempts,0)+$increment",
            write=True,
            key=fingerprint([self.key, row["id"]]),
            scope=self.scope,
            chunk=row["id"],
            hash=row["content_hash"],
            profile=json.dumps(self.profile, sort_keys=True),
            state="failed" if error else "processing",
            error=error,
            timestamp=now_ms(),
            increment=0 if error else 1,
        )

    def write_chunk(self, row, result):
        if self.rows.get(row["id"]) != row or result != validate_extraction(
            result["payload"], row, self.key
        ):
            raise ValueError("Extraction outside canonical graph generation")
        evidence = self.evidence(row, result)
        document = self.document(row)

        @unit_of_work(timeout=120)
        def write(tx):
            def run(query, **params):
                return tx.run(query, **params)

            found = run(
                "MATCH (c:RAGVectorChunk {key:$key, partition:$partition, organization_id:$org, project_id:$project}) "
                "WHERE c.id=$id AND c.content_hash=$hash AND c.content=$content AND c.generation_id=$generation RETURN c.key",
                key=self.vectors.properties(row)["key"],
                partition=self.vectors.key,
                org=self.scope["organization_id"],
                project=self.scope["project_id"],
                id=row["id"],
                hash=row["content_hash"],
                content=row["content"],
                generation=row["generation_id"],
            ).data()
            if len(found) != 1:
                raise ValueError("Canonical vector chunk missing or changed")
            run(
                "MATCH (e:RAGEvidence {graph_key:$graph, chunk_id:$chunk}) DETACH DELETE e",
                graph=self.key,
                chunk=row["id"],
            ).consume()
            run(
                "MATCH (c:RAGVectorChunk {key:$key})-[m:MENTIONS {graph_key:$graph}]->() DELETE m",
                key=self.vectors.properties(row)["key"],
                graph=self.key,
            ).consume()
            run(
                "MERGE (d:RAGEndpoint:RAGGraphDocument {key:$key}) SET d=$properties",
                key=document["key"],
                properties=document,
            ).consume()
            for entity in result["entities"]:
                properties = self.scope | {
                    "key": entity["key"],
                    "id": entity["key"],
                    "type": entity["type"],
                    "name": entity["name"],
                }
                # Type is a backend-validated enum, never an arbitrary model-supplied Cypher identifier.
                run(
                    f"MERGE (e:RAGEndpoint:RAGEntity:{entity['type']} {{key:$key}}) SET e += $properties "
                    "WITH e MATCH (c:RAGVectorChunk {key:$chunk}) MERGE (c)-[:MENTIONS {graph_key:$graph}]->(e)",
                    key=entity["key"],
                    properties=properties,
                    chunk=self.vectors.properties(row)["key"],
                    graph=self.key,
                ).consume()
            for assertion in result["assertions"]:
                properties = (
                    self.scope
                    | {
                        key: assertion[key]
                        for key in ("key", "source", "target", "relation")
                    }
                    | {"id": assertion["key"]}
                )
                written = run(
                    "MATCH (s:RAGEndpoint {key:$source,graph_key:$graph}), (t:RAGEntity {key:$target,graph_key:$graph}) "
                    "MERGE (a:RAGAssertion {key:$key}) SET a=$properties WITH a,s,t "
                    "OPTIONAL MATCH (a)-[old:SUBJECT|OBJECT]->() DELETE old WITH DISTINCT a,s,t "
                    "MERGE (a)-[:SUBJECT]->(s) MERGE (a)-[:OBJECT]->(t) RETURN a.key",
                    source=assertion["source"],
                    target=assertion["target"],
                    graph=self.key,
                    key=assertion["key"],
                    properties=properties,
                ).data()
                if len(written) != 1:
                    raise ValueError("Assertion endpoint missing")
            for item in evidence.values():
                target_label = (
                    "RAGEntity" if item["kind"] == "mention" else "RAGAssertion"
                )
                written = run(
                    f"MATCH (t:{target_label} {{key:$target,graph_key:$graph}}), (c:RAGVectorChunk {{key:$chunk}}) "
                    "MERGE (e:RAGEvidence {key:$key}) SET e=$properties MERGE (e)-[:SUPPORTS]->(t) MERGE (e)-[:FROM_CHUNK]->(c) RETURN e.key",
                    target=item["target_key"],
                    graph=self.key,
                    chunk=self.vectors.properties(row)["key"],
                    key=item["key"],
                    properties=item,
                ).data()
                if len(written) != 1:
                    raise ValueError("Evidence endpoint missing")
            run(
                "MATCH (a:RAGAssertion {graph_key:$graph}) WHERE NOT EXISTS {MATCH (:RAGEvidence)-[:SUPPORTS]->(a)} DETACH DELETE a",
                graph=self.key,
            ).consume()
            run(
                "MATCH (e:RAGEntity {graph_key:$graph}) WHERE NOT EXISTS {MATCH (:RAGEvidence)-[:SUPPORTS]->(e)} DETACH DELETE e",
                graph=self.key,
            ).consume()
            run(
                "MERGE (x:RAGExtraction {key:$key}) SET x += $scope, x.chunk_id=$chunk_id, x.content_hash=$hash, "
                "x.profile_json=$profile, x.result_json=$result, x.result_hash=$result_hash, x.state=$state, x.error_code=null, x.updated_at=$timestamp "
                "WITH x OPTIONAL MATCH (x)-[old:FROM_CHUNK]->() DELETE old WITH DISTINCT x "
                "MATCH (c:RAGVectorChunk {key:$chunk_key}) MERGE (x)-[:FROM_CHUNK]->(c)",
                key=fingerprint([self.key, row["id"]]),
                scope=self.scope,
                chunk_id=row["id"],
                hash=row["content_hash"],
                profile=json.dumps(self.profile, sort_keys=True),
                result=json.dumps(result["payload"], sort_keys=True),
                result_hash=fingerprint(result),
                state="extracted" if result["entities"] else "empty",
                timestamp=now_ms(),
                chunk_key=self.vectors.properties(row)["key"],
            ).consume()

        with self.vectors.driver.session(default_access_mode="WRITE") as session:
            session.execute_write(write)

    def integrity(self, complete=True):
        # shortcut: recompute full graph proofs on reads; add invalidatable publication proofs before high-volume serving.
        records = self.cached()
        if set(records) - self.rows.keys():
            raise ValueError("Foreign extraction record")
        (
            expected_evidence,
            expected_entities,
            expected_assertions,
            expected_documents,
        ) = ({}, {}, {}, {})
        valid, failures, empty = 0, [], 0
        for chunk_id, row in self.rows.items():
            record = records.get(chunk_id, {})
            result = self.cached_result(row, record, require_success=False)
            if result is None or record.get("state") not in {"extracted", "empty"}:
                failures.append(
                    {
                        "chunk_id": chunk_id,
                        "code": record.get("error_code")
                        or record.get("state")
                        or "pending",
                    }
                )
            else:
                valid += 1
                empty += not bool(result["entities"])
            if result is None:
                continue
            expected_documents[self.document(row)["key"]] = self.document(row)
            expected_evidence.update(self.evidence(row, result))
            for entity in result["entities"]:
                expected_entities.setdefault(
                    entity["key"], {"type": entity["type"], "names": set()}
                )["names"].add(entity["name"])
            for assertion in result["assertions"]:
                expected_assertions[assertion["key"]] = (
                    self.scope
                    | {
                        key: assertion[key]
                        for key in ("key", "source", "target", "relation")
                    }
                    | {"id": assertion["key"]}
                )
        actual_evidence = self.vectors._run(
            "MATCH (e:RAGEvidence {graph_key:$graph}) OPTIONAL MATCH (e)-[:FROM_CHUNK]->(c) "
            "WITH e,collect(c.key) AS chunks OPTIONAL MATCH (e)-[:SUPPORTS]->(t) RETURN properties(e) AS evidence,chunks,collect(t.key) AS targets",
            graph=self.key,
        )
        seen = set()
        for record in actual_evidence:
            item = record["evidence"]
            expected = expected_evidence.get(item.get("key"))
            if (
                expected != item
                or item["key"] in seen
                or record["targets"] != [item["target_key"]]
                or record["chunks"]
                != [self.vectors.properties(self.rows[item["chunk_id"]])["key"]]
            ):
                raise ValueError("Graph evidence integrity failed")
            seen.add(item["key"])
        if seen != expected_evidence.keys():
            raise ValueError("Graph evidence missing")
        actual_entities = self.vectors._run(
            "MATCH (e:RAGEntity {graph_key:$graph}) RETURN properties(e) AS entity,labels(e) AS labels",
            graph=self.key,
        )
        seen = set()
        for record in actual_entities:
            item = record["entity"]
            expected = expected_entities.get(item.get("key"))
            if (
                not expected
                or item["key"] in seen
                or item.get("id") != item["key"]
                or item.get("type") != expected["type"]
                or item.get("name") not in expected["names"]
                or not {"RAGEntity", "RAGEndpoint"}.issubset(record["labels"])
                or set(record["labels"]) & set(ENTITY_TYPES) != {expected["type"]}
                or any(item.get(k) != v for k, v in self.scope.items())
            ):
                raise ValueError("Graph entity integrity failed")
            seen.add(item["key"])
        if seen != expected_entities.keys():
            raise ValueError("Graph entity missing")
        assertions = self.vectors._run(
            "MATCH (a:RAGAssertion {graph_key:$graph}) OPTIONAL MATCH (a)-[:SUBJECT]->(s) "
            "WITH a,collect(s.key) AS subjects OPTIONAL MATCH (a)-[:OBJECT]->(t) "
            "RETURN properties(a) AS assertion,subjects,collect(t.key) AS targets",
            graph=self.key,
        )
        seen = set()
        for record in assertions:
            item = record["assertion"]
            if (
                expected_assertions.get(item.get("key")) != item
                or record["subjects"] != [item["source"]]
                or record["targets"] != [item["target"]]
            ):
                raise ValueError("Graph assertion integrity failed")
            seen.add(item["key"])
        if seen != expected_assertions.keys():
            raise ValueError("Graph assertion missing")
        documents = self.vectors._run(
            "MATCH (d:RAGGraphDocument {graph_key:$graph}) RETURN properties(d) AS document",
            graph=self.key,
        )
        if (
            len(documents) != len(expected_documents)
            or {record["document"]["key"]: record["document"] for record in documents}
            != expected_documents
        ):
            raise ValueError("Graph source document integrity failed")
        if complete and (not self.rows or valid != len(self.rows)):
            raise ValueError("Graph extraction incomplete")
        self.verified_evidence, self.verified_assertions = (
            expected_evidence,
            expected_assertions,
        )
        return {
            "expected_chunks": len(self.rows),
            "valid_extractions": valid,
            "empty_extractions": empty,
            "entities": len(expected_entities),
            "assertions": len(expected_assertions),
            "evidence_spans": len(expected_evidence),
            "entity_types": dict(
                Counter(item["type"] for item in expected_entities.values())
            ),
            "relation_types": dict(
                Counter(item["relation"] for item in expected_assertions.values())
            ),
            "provenance": {
                "verified_spans": len(expected_evidence),
                "total_spans": len(actual_evidence),
                "dangling_spans": 0,
            },
            "assertion_samples": [
                assertion
                | {
                    "evidence": [
                        span
                        for span in expected_evidence.values()
                        if span["target_key"] == assertion["key"]
                    ][:3]
                }
                for assertion in list(expected_assertions.values())[:8]
            ],
            "failures": failures,
            "graph_key": self.key,
            "state": (
                "verified_unpublished"
                if valid == len(self.rows) and expected_assertions
                else "graph_partial"
            ),
        }

    def build(self, extractor, max_chunks=0):
        if extractor.key != self.key or type(max_chunks) is not int or max_chunks < 0:
            raise ValueError("Extractor generation or chunk limit mismatch")
        self.require_vectors()
        self.prepare()
        self.withdraw()
        records, attempted, reused = self.cached(), 0, 0
        for row in self.rows.values():
            result = self.cached_result(row, records.get(row["id"], {}))
            if result is None:
                if max_chunks and attempted >= max_chunks:
                    continue
                self.attempt(row)
                attempted += 1
                try:
                    result = extractor.extract(row)
                except ExtractionError as exc:
                    self.attempt(row, str(exc))
                    continue
            else:
                reused += 1
            # shortcut: replay cached graph writes for repair; add per-chunk storage proofs when repeat runs become costly.
            try:
                self.write_chunk(row, result)
            except (
                Exception
            ) as exc:  # noqa: BLE001 - preserve safe per-chunk storage failure and continue independent work
                self.attempt(row, type(exc).__name__)
            logging.getLogger(__name__).info(
                "Graph checkpoint attempted=%s reused=%s expected=%s",
                attempted,
                reused,
                len(self.rows),
            )
        return self.integrity(complete=False) | {
            "attempted": attempted,
            "reused": reused,
        }

    def publish(self):
        self.require_vectors()
        status = self.integrity()
        if not status["assertions"]:
            raise ValueError("Graph has no supported assertions")
        self.vectors._run(
            "MERGE (p:RAGGraphPublication {key:$key}) SET p += $scope, p.profile_json=$profile, p.verified_at=$timestamp",
            write=True,
            key=self.key,
            scope=self.scope,
            profile=json.dumps(self.profile, sort_keys=True),
            timestamp=now_ms(),
        )

    def withdraw(self):
        self.vectors._run(
            "MATCH (p:RAGGraphPublication {key:$key}) DELETE p",
            write=True,
            key=self.key,
        )

    def require_vectors(self):
        try:
            self.vectors.require_publication()
        except ValueError:
            raise ValueError("Stage C vector publication required") from None

    def require_publication(self):
        publications = self.vectors._run(
            "MATCH (p:RAGGraphPublication {key:$key}) RETURN properties(p) AS publication",
            key=self.key,
        )
        expected = self.scope | {
            "profile_json": json.dumps(self.profile, sort_keys=True)
        }
        if len(publications) != 1 or any(
            publications[0]["publication"].get(k) != v for k, v in expected.items()
        ):
            raise ValueError("Graph generation not published")
        self.require_vectors()
        status = self.integrity()
        if not status["assertions"]:
            raise ValueError("Graph has no supported assertions")
        return status

    def neighbors(self, row, fanout):
        common = "MATCH (seed:RAGVectorChunk {key:$seed})<-[:FROM_CHUNK]-(left:RAGEvidence {graph_key:$graph}) "
        finish = (
            " MATCH (entity)<-[:SUPPORTS]-(right:RAGEvidence {graph_key:$graph,kind:'mention'})-[:FROM_CHUNK]->(chunk:RAGVectorChunk) "
            "WHERE chunk.key<>seed.key AND chunk.partition=$partition AND chunk.organization_id=$org AND chunk.project_id=$project "
            "RETURN chunk.id AS chunk_id,properties(left) AS left,properties(right) AS right,entity.key AS entity_key,"
        )
        params = {
            "seed": self.vectors.properties(row)["key"],
            "graph": self.key,
            "partition": self.vectors.key,
            "org": self.scope["organization_id"],
            "project": self.scope["project_id"],
            "limit": fanout,
        }
        assertions = self.vectors._run(
            common
            + "-[:SUPPORTS]->(a:RAGAssertion {graph_key:$graph})-[:OBJECT]->(entity:RAGEntity {graph_key:$graph}) "
            + finish
            + "a.relation AS relation,a.key AS assertion_key ORDER BY chunk_id,left.key,right.key LIMIT $limit",
            **params,
        )
        mentions = self.vectors._run(
            common
            + "-[:SUPPORTS]->(entity:RAGEntity {graph_key:$graph}) "
            + finish
            + "'SHARED_ENTITY' AS relation,null AS assertion_key ORDER BY chunk_id,left.key,right.key LIMIT $limit",
            **params,
        )
        return assertions + mentions

    def search(
        self,
        provider,
        query,
        seed_limit=4,
        hops=2,
        fanout=8,
        evidence_limit=24,
        require_publication=True,
    ):
        if any(
            type(value) is not int
            for value in (seed_limit, hops, fanout, evidence_limit)
        ) or not (
            1 <= seed_limit <= 8
            and 1 <= hops <= 2
            and 1 <= fanout <= 20
            and seed_limit <= evidence_limit <= 40
        ):
            raise ValueError("Graph retrieval budget exceeded")
        if require_publication:
            self.require_publication()
        else:
            self.integrity()
        seeds = self.vectors.search(provider, query, seed_limit)
        found = {
            item["chunk"]["id"]: {
                "chunk": item["chunk"],
                "score": item["score"],
                "method": "vector_seed",
                "path": [],
            }
            for item in seeds
        }
        frontier = list(found)
        for depth in range(hops):
            following = []
            for chunk_id in frontier:
                for edge in self.neighbors(self.rows[chunk_id], fanout)[:fanout]:
                    target = edge["chunk_id"]
                    if target not in self.rows or any(
                        edge[side].get(key) != value
                        for side in ("left", "right")
                        for key, value in self.scope.items()
                    ):
                        raise ValueError("Foreign graph evidence")
                    if (
                        edge["left"].get("chunk_id") != chunk_id
                        or edge["right"].get("chunk_id") != target
                        or any(
                            self.verified_evidence.get(edge[side].get("key"))
                            != edge[side]
                            for side in ("left", "right")
                        )
                        or edge["right"].get("target_key") != edge["entity_key"]
                    ):
                        raise ValueError("Graph path evidence changed")
                    if edge["assertion_key"]:
                        assertion = self.verified_assertions.get(edge["assertion_key"])
                        if (
                            not assertion
                            or assertion["relation"] != edge["relation"]
                            or assertion["target"] != edge["entity_key"]
                            or edge["left"].get("target_key") != edge["assertion_key"]
                        ):
                            raise ValueError("Graph path assertion changed")
                    elif (
                        edge["relation"] != "SHARED_ENTITY"
                        or edge["left"].get("target_key") != edge["entity_key"]
                    ):
                        raise ValueError("Unsupported graph path")
                    if target in found:
                        continue
                    if len(found) >= evidence_limit:
                        break
                    found[target] = {
                        "chunk": self.rows[target],
                        "score": None,
                        "method": "graph_expansion",
                        "path": found[chunk_id]["path"]
                        + [edge | {"from_chunk_id": chunk_id, "hop": depth + 1}],
                    }
                    following.append(target)
            frontier = following
            if not frontier or len(found) >= evidence_limit:
                break
        added = len(found) - len(seeds)
        return {
            "mode": "graph",
            "path": "semantic_seeds_then_evidence_graph",
            "graph_key": self.key,
            "seed_count": len(seeds),
            "graph_added": added,
            "state": "graph_evidence" if added else "no_connected_evidence",
            "budgets": {
                "seeds": seed_limit,
                "hops": hops,
                "fanout": fanout,
                "evidence": evidence_limit,
            },
            "results": list(found.values()),
        }
