import os
import json
from openai import OpenAI

client = OpenAI(base_url="http://localhost:3000/v1", api_key=os.environ["RECALL_API_KEY"])
response = client.chat.completions.create(
    model="platform:default",
    messages=[{"role": "user", "content": "Which is the most horrific case from them all"}],
    extra_body={"corpus_id": "proj_145d51a36a304ca49d8c05624e435d50", "mode": "vector"},
    stream=True,
)
for chunk in response:
    if chunk.choices:
        print(chunk.choices[0].delta.content or "", end="", flush=True)
    if (chunk.model_extra or {}).get("citations"):
        print("\nCitations:", json.dumps(chunk.model_extra["citations"]))

