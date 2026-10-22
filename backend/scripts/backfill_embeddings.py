"""Retired unsafe Turso backfill; retained as an explicit CLI error."""


def main():
    raise SystemExit(
        "Legacy Turso backfill disabled. Stage C must verify Neo4j generation/model provenance before indexing."
    )


if __name__ == "__main__":
    main()
