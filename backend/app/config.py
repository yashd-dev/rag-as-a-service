from pathlib import Path
import os

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)


class Config:
    BACKEND_INTERNAL_SECRET = os.getenv("BACKEND_INTERNAL_SECRET", "")
    CREDENTIAL_ENCRYPTION_KEY = os.getenv("CREDENTIAL_ENCRYPTION_KEY", "")
    TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL") or os.getenv("TURSO_CONNECTION_URL", "")
    TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "")
    UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "backend/storage/uploads"))
    TMP_DIR = Path(os.getenv("TMP_DIR", "backend/storage/tmp"))
    MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "100"))
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password123")
