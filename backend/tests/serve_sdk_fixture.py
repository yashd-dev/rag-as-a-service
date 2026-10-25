"""Disposable HTTP fixture for actual external SDK protocol checks; no live models."""

import argparse
import faulthandler
import json
import os
from pathlib import Path

import pytest
from werkzeug.serving import make_server

from backend.app.services import query_service
from backend.app.services.api_keys import ApiKeys
from backend.app.services.auth_context import AuthContext
from backend.tests.conftest import store
from backend.tests.test_query_api import api


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    patch = pytest.MonkeyPatch()
    local = store.__wrapped__(args.directory)
    app, _, _, _, _, _, _, _ = api.__wrapped__(local, patch)
    app.config.update(PLATFORM_LLM_BASE_URL="https://fixture.invalid/v1", PLATFORM_LLM_API_KEY="fixture-only", PLATFORM_LLM_MODEL="fixture-only-model")
    controlled = query_service.generate_grounded
    patch.setattr(query_service, "generate_grounded", lambda config, messages, **kwargs: controlled(config, messages))
    key = ApiKeys(app.config).create(AuthContext("u", "o", "owner"), {"name": "SDK fixture", "corpus_ids": ["p"]})
    server = make_server("127.0.0.1", 0, app, threaded=True)
    faulthandler.dump_traceback_later(8)
    with os.fdopen(os.open(args.directory / "ready.json", os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "w") as output:
        json.dump({"baseUrl": f"http://127.0.0.1:{server.server_port}/v1", "key": key["key"], "key_id": key["id"], "corpus_id": "p"}, output)
    server.serve_forever()


if __name__ == "__main__":
    main()
