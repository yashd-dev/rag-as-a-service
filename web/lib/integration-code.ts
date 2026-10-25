import type { RetrievalMode } from "@/lib/rag-contract";

export type IntegrationSelection = { baseUrl: string; corpusId: string; model: string; message: string; mode: RetrievalMode; stream: boolean };

export function integrationExamples(selection: IntegrationSelection) {
  const { baseUrl, corpusId, model, mode, stream } = selection;
  const message = selection.message.trim() || "What does the indexed evidence say?";
  const literal = JSON.stringify;
  const body = { model, messages: [{ role: "user", content: message }], corpus_id: corpusId, mode, stream };
  const shell = (text: string) => "'" + text.replaceAll("'", "'\"'\"'") + "'";
  return {
    python: `import os\nimport json\nfrom openai import OpenAI\n\nclient = OpenAI(base_url=${literal(baseUrl)}, api_key=os.environ["RECALL_API_KEY"])\nresponse = client.chat.completions.create(\n    model=${literal(model)},\n    messages=[{"role": "user", "content": ${literal(message)}}],\n    extra_body={"corpus_id": ${literal(corpusId)}, "mode": ${literal(mode)}},\n    stream=${stream ? "True" : "False"},\n)\n${stream ? `for chunk in response:\n    if chunk.choices:\n        print(chunk.choices[0].delta.content or "", end="", flush=True)\n    if (chunk.model_extra or {}).get("citations"):\n        print("\\nCitations:", json.dumps(chunk.model_extra["citations"]))` : `print(response.choices[0].message.content)\nprint(json.dumps((response.model_extra or {}).get("citations", [])))`}\n`,
    javascript: `import OpenAI from "openai";\n\nconst client = new OpenAI({ baseURL: ${literal(baseUrl)}, apiKey: process.env.RECALL_API_KEY });\nconst response = await client.chat.completions.create(${JSON.stringify(body, null, 2)});\n${stream ? `for await (const chunk of response) {\n  process.stdout.write(chunk.choices[0]?.delta.content || "");\n  if (chunk.citations) console.log("\\nCitations:", chunk.citations);\n}` : `console.log(response.choices[0].message.content);\nconsole.log(response.citations);`}\n`,
    curl: `curl --fail-with-body${stream ? " --no-buffer" : ""} ${shell(baseUrl.replace(/\/$/, "") + "/chat/completions")} \\\n  -H "Authorization: Bearer $RECALL_API_KEY" \\\n  -H "Content-Type: application/json" \\\n  --data ${shell(JSON.stringify(body))}\n`,
  };
}
