import sqlite3

import pytest

from backend.app.services.neo4j_vectors import canonical_snapshot
from backend.scripts import index_vectors


def test_snapshot_preserves_source_spans_and_invalidates_on_change(store):
    repo, path, project = store
    first = repo.stage(
        project, "source", "record", "A real source passage.", {"source_uri": "source"}
    )
    config = {"TURSO_DATABASE_URL": repo.url, "TURSO_AUTH_TOKEN": repo.token}
    snapshot = canonical_snapshot(config, project)
    assert snapshot["rows"][0]["generation_id"] == first["generation"]
    assert snapshot["rows"][0]["start_char"] == 0
    repo.stage(project, "source", "record", "A changed source passage.")
    assert canonical_snapshot(config, project)["manifest"] != snapshot["manifest"]
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE canonical_chunks SET content='corrupt'")
    with pytest.raises(ValueError, match="not text ready"):
        canonical_snapshot(config, project)
    with pytest.raises(ValueError, match="not found"):
        canonical_snapshot(config, project | {"organization_id": "foreign"})


def test_vector_plan_never_probes_model_or_connects_to_neo4j(
    store, tmp_path, monkeypatch, capsys
):
    repo, path, _ = store
    env = tmp_path / "plan.env"
    env.write_text(f"TURSO_DATABASE_URL={repo.url}\nTURSO_AUTH_TOKEN=local\n")

    def forbidden(*args, **kwargs):
        pytest.fail("Dry run must not probe or write retrieval data")

    monkeypatch.setattr(index_vectors, "EmbeddingGemmaProvider", forbidden)
    monkeypatch.setattr(index_vectors, "Neo4jVectorStore", forbidden)
    before = path.read_bytes()
    assert (
        index_vectors.main(
            ["--env-file", str(env), "--organization-id", "o", "--project-id", "p"]
        )
        == 0
    )
    assert path.read_bytes() == before
    assert '"dry_run": true' in capsys.readouterr().out
