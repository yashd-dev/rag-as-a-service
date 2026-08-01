import os

from dotenv import load_dotenv
from google import genai
from sentence_transformers import SentenceTransformer

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise ValueError("GEMINI_API_KEY not found.")

client = genai.Client(
    api_key=API_KEY
)

LLM_MODEL = "gemini-2.5-flash"

embedding_model = SentenceTransformer(
    "BAAI/bge-small-en-v1.5"
)
