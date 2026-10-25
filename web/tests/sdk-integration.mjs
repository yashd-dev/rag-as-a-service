import assert from "node:assert/strict";
import { access, mkdtemp } from "node:fs/promises";
import { resolve } from "node:path";
import OpenAI from "openai";
import { generateText, streamText } from "ai";
import { createOpenAICompatible } from "@ai-sdk/openai-compatible";
import { integrationExamples } from "../lib/integration-code.ts";

const root = resolve(import.meta.dir, "../..");
const directory = await mkdtemp("/tmp/opencode/sdk-proof-");
const server = Bun.spawn([root + "/.venv/bin/python", "-m", "backend.tests.serve_sdk_fixture", "--directory", directory], { cwd: root, stdout: "ignore", stderr: "pipe" });
const serverErrors = new Response(server.stderr).text();
try {
  const readyPath = directory + "/ready.json";
  const exists = () => access(readyPath).then(() => true, () => false);
  for (let n = 0; n < 200 && !await exists(); n++) await Bun.sleep(100);
  if (!await exists()) {
    server.kill();
    throw new Error("SDK fixture did not start: " + await serverErrors);
  }
  const setup = await Bun.file(readyPath).json();
  const client = new OpenAI({ baseURL: setup.baseUrl, apiKey: setup.key, maxRetries: 0, timeout: 10_000 });
  const payload = { model: "platform:default", corpus_id: setup.corpus_id, messages: [{ role: "user", content: "vector question" }] };
  const expected = "The supplied evidence is available [S1]";
  const models = await client.models.list();
  assert.ok(models.data.some(item => item.id === "platform:default"));
  const response = await client.chat.completions.create(payload);
  assert.equal(response.choices[0].message.content, expected);
  assert.equal(response.citations.length, 1);
  const source = await fetch(new URL(response.citations[0].source_view_url, setup.baseUrl), { headers: { Authorization: "Bearer " + setup.key } }).then(r => r.json());
  assert.equal(source.content, response.citations[0].excerpt);
  console.log("PASS: OpenAI JavaScript 7.43.0 JSON, discovery and authorized citations");
  let text = "", citations;
  for await (const chunk of await client.chat.completions.create({ ...payload, stream: true })) {
    text += chunk.choices[0]?.delta.content || "";
    if (chunk.citations) citations = chunk.citations;
  }
  assert.equal(text, expected); assert.equal(citations.length, 1);
  console.log("PASS: OpenAI JavaScript SSE termination and citation extension");

  const provider = createOpenAICompatible({ name: "recall", baseURL: setup.baseUrl, apiKey: setup.key, includeUsage: true });
  const options = { model: provider.chatModel("platform:default"), prompt: "vector question", providerOptions: { recall: { corpus_id: "p", mode: "vector" } }, maxRetries: 0 };
  const generated = await generateText({ ...options, include: { responseBody: true } });
  assert.equal(generated.text, expected);
  assert.equal(generated.response.body.citations.length, 1);
  text = ""; citations = undefined;
  const streamed = streamText({ ...options, includeRawChunks: true });
  for await (const part of streamed.fullStream) {
    if (part.type === "text-delta") text += part.text;
    if (part.type === "raw" && part.rawValue.citations) citations = part.rawValue.citations;
    if (part.type === "error") throw part.error;
  }
  assert.equal(text, expected); assert.equal(citations.length, 1);
  console.log("PASS: Vercel AI SDK 7.0.153 / openai-compatible 3.0.78 JSON and SSE with citations");

  for (const streaming of [false, true]) {
    const examples = integrationExamples({ baseUrl: setup.baseUrl, corpusId: "p", model: "platform:default", message: "vector question", mode: "vector", stream: streaming });
    for (const [language, command] of [["Python OpenAI", [root + "/.venv/bin/python", "-c", examples.python]], ["cURL", ["bash", "-c", examples.curl]]]) {
      const process = Bun.spawn(command, { env: { ...Bun.env, RECALL_API_KEY: setup.key }, stdout: "pipe", stderr: "pipe" });
      const output = await new Response(process.stdout).text();
      const error = await new Response(process.stderr).text();
      assert.equal(await process.exited, 0, error);
      assert.ok(streaming && language === "cURL" ? output.includes("[DONE]") && output.includes("citations") : output.includes(expected));
      console.log(`PASS: generated ${language} ${streaming ? "streaming" : "JSON"} example executes`);
    }
  }
  await assert.rejects(client.chat.completions.create({ ...payload, corpus_id: "foreign" }), error => error.status === 403);
  console.log("PASS: actual SDK scope denial");
  console.log("SDK_INTEGRATION_COMPLETE");
} catch (error) {
  server.kill();
  await server.exited;
  console.error(await serverErrors);
  throw error;
} finally {
  server.kill();
  await server.exited;
}
