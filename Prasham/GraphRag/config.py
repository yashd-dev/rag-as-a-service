import os

from dotenv import load_dotenv
from openai import OpenAI
from sentence_transformers import SentenceTransformer

load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY")

if not API_KEY:
    raise ValueError("OPENAI_API_KEY not found.")

client = OpenAI(
    api_key=API_KEY
)

LLM_MODEL = "gpt-5.6-luna"


def generate_text(prompt):
    response = client.responses.create(
        model=LLM_MODEL,
        input=prompt
    )

    return response.output_text

embedding_model = SentenceTransformer(
    "BAAI/bge-small-en-v1.5"
)
