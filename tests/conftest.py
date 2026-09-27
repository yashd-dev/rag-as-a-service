import pytest

from backend.app import create_app
from backend.app.config import Config


class TestConfig(Config):
    TESTING = True
    BACKEND_INTERNAL_SECRET = "test-secret"
    CREDENTIAL_ENCRYPTION_KEY = "test-encryption-key"
    TURSO_DATABASE_URL = "libsql://test-db.turso.io"
    TURSO_AUTH_TOKEN = "test-token"


@pytest.fixture()
def app():
    return create_app(TestConfig)


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth_headers():
    return {
        "X-Internal-Secret": "test-secret",
        "X-User-Id": "user_1",
        "X-Organization-Id": "org_1",
        "X-User-Role": "owner",
    }
