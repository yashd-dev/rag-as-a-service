import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)


class Config:
    BACKEND_INTERNAL_SECRET = os.getenv("BACKEND_INTERNAL_SECRET", "")
    CREDENTIAL_ENCRYPTION_KEY = os.getenv("CREDENTIAL_ENCRYPTION_KEY", "")
    TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL") or os.getenv(
        "TURSO_CONNECTION_URL", ""
    )
    TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "")
    PLATFORM_LLM_BASE_URL = os.getenv(
        "PLATFORM_LLM_BASE_URL",
        "https://generativelanguage.googleapis.com/v1beta/openai",
    )
    PLATFORM_LLM_API_KEY = os.getenv("PLATFORM_LLM_API_KEY") or os.getenv(
        "GEMINI_API_KEY", ""
    )
    PLATFORM_LLM_MODEL = os.getenv("PLATFORM_LLM_MODEL", "gemini-2.5-flash")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "")
    MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
    MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "")
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    GRAPH_LLM_MODEL = os.getenv("GRAPH_LLM_MODEL", "smollm2:135m")
    GRAPH_EXTRACTION_STRATEGY = os.getenv("GRAPH_EXTRACTION_STRATEGY", "full_legal")
    GRAPH_LLM_TIMEOUT_SECONDS = os.getenv("GRAPH_LLM_TIMEOUT_SECONDS", "60")
    GRAPH_LLM_NUM_PREDICT = int(os.getenv("GRAPH_LLM_NUM_PREDICT", "700"))
    GRAPH_LLM_NUM_CTX = int(os.getenv("GRAPH_LLM_NUM_CTX", "4096"))
    GRAPH_EXTRACTION_MAX_CHUNKS = int(os.getenv("GRAPH_EXTRACTION_MAX_CHUNKS", "0"))
    GRAPH_CHUNK_SIZE = int(os.getenv("GRAPH_CHUNK_SIZE", "300"))
    GRAPH_CHUNK_OVERLAP = int(os.getenv("GRAPH_CHUNK_OVERLAP", "30"))
    OLLAMA_EMBEDDING_MODEL = os.getenv("OLLAMA_EMBEDDING_MODEL", "embeddinggemma")
    EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "16"))
    FALLBACK_LLM_MODEL = os.getenv("FALLBACK_LLM_MODEL", "smollm2:135m")
    UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "backend/storage/uploads"))
    TMP_DIR = Path(os.getenv("TMP_DIR", "backend/storage/tmp"))
    MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "100"))
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password123")
    UNSTRUCTURED_API_KEY = os.getenv("UNSTRUCTURED_API_KEY", "")
    UNSTRUCTURED_API_URL = os.getenv("UNSTRUCTURED_API_URL") or os.getenv(
        "UNSTRUCTURED_API_UR", ""
    )
    UNSTRUCTURED_POLL_SECONDS = int(os.getenv("UNSTRUCTURED_POLL_SECONDS", "10"))
    UNSTRUCTURED_PARTITION_STRATEGY = os.getenv(
        "UNSTRUCTURED_PARTITION_STRATEGY", "hi_res"
    )
