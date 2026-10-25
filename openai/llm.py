import json
import os

from openai import OpenAI


client = OpenAI(
    base_url="http://localhost:3000/v1",
    api_key=os.environ["RECALL_API_KEY"],
)
response = client.chat.completions.create(
    model="credential:cred_73592e95eddc4c73994836ef7d42db61",
    messages=[{"role": "user", "content": "will the bug be there if it ran on neptune"}],
    extra_body={
        "corpus_id": "proj_1096bbd2f2074f398ab5dea404f3f4b4",
        "mode": "vector",
    },
    stream=True,
)
for chunk in response:
    if chunk.choices:
        print(chunk.choices[0].delta.content or "", end="", flush=True)
    if (chunk.model_extra or {}).get("citations"):
        print("\nCitations:", json.dumps(chunk.model_extra["citations"]))
