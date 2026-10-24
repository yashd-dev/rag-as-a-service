import { afterEach, expect, mock, test } from "bun:test";
import { modeAvailable, parsePassage, parseQueryResult, parseReadiness, passageHref, safeSourceUri } from "../lib/rag-contract.ts";

mock.module("@/lib/dashboard-context", () => ({
  getDashboardContext: async () => ({ session: { user: { id: "u" } }, organization: { id: "o" }, role: "member" }),
}));
mock.module("next/navigation", () => ({ redirect: () => { throw new Error("Unexpected redirect"); }, unstable_rethrow: () => {} }));
mock.module("next/cache", () => ({ revalidatePath: () => {} }));
const { backendRequest, BackendError, listProjects, listDocuments, queryProject, sourcePassage } = await import("../lib/backend.ts");
const { queryProjectAction } = await import("../lib/backend-actions.ts");
const originalFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = originalFetch; });

const source = {
  citation_id: "cit_a", label: "S1", chunk_id: "chunk-a", document_id: "doc-a", generation_id: "gen-a",
  file_name: "Actual fixture", excerpt: "Source evidence.", content_hash: "hash", start_char: 0, end_char: 16,
  pages: [], source_uri: null, score: 0.8, fusion_score: null, retrieval_methods: ["vector"], retrieval_path: [],
};
const result = {
  project_id: "p", query_run_id: "run", mode: "vector", status: "answered", answer: "Supported [S1]",
  sources: [source], citation_candidates: [source], used_citation_ids: [source.citation_id],
  generation: { provider: "fixture", model: "controlled", fallback: false, called: true },
  vector_generation: "partition", graph_generation: null,
  retrieval_diagnostics: { path: "neo4j_vector", ranking: "cosine", candidate_count: 1, context_count: 1, graph_added: 0, retrieval_ms: 10, generation_ms: 20 },
};
const readiness = { project_id: "p", state: "graph_partial", capabilities: { text: true, vector: true, graph: false }, counts: { total: 1, pending: 0, excluded: 0 }, verified_at: 1 };

test("partial graph keeps vector usable, refuses graph/hybrid; empty corpus parses", () => {
  const parsed = parseReadiness(readiness);
  expect(parsed.failures).toEqual([]);
  expect(modeAvailable(parsed, "vector")).toBe(true);
  expect(modeAvailable(parsed, "graph")).toBe(false);
  expect(modeAvailable(parsed, "hybrid")).toBe(false);
  expect(modeAvailable(null, "vector")).toBe(false);
  expect(parseReadiness({ ...readiness, counts: { total: 0 }, capabilities: { text: false, vector: false, graph: false } }).counts.total).toBe(0);
  expect(() => parseReadiness({ ...readiness, capabilities: { vector: "true" } })).toThrow();
  expect(() => parseReadiness(readiness, "foreign")).toThrow();
});

test("query contracts reject foreign modes/projects, malformed sources and false answers", () => {
  expect(parseQueryResult(result, "p", "vector").answer).toBe(result.answer);
  expect(() => parseQueryResult(result, "foreign", "vector")).toThrow();
  expect(() => parseQueryResult(result, "p", "hybrid")).toThrow();
  expect(() => parseQueryResult({ ...result, sources: [{ ...source, pages: "invented" }] }, "p", "vector")).toThrow();
  expect(() => parseQueryResult({ ...result, used_citation_ids: [] }, "p", "vector")).toThrow();
  expect(() => parseQueryResult({ ...result, answer: "Unsupported [S2]" }, "p", "vector")).toThrow();
  expect(() => parseQueryResult({ ...result, sources: [], used_citation_ids: [] }, "p", "vector")).toThrow();
  expect(parseQueryResult({ ...result, status: "insufficient_evidence", answer: "Insufficient support", sources: [], used_citation_ids: [] }, "p", "vector").status).toBe("insufficient_evidence");
});

test("passage IDs/text must match; links escape IDs and reject unsafe external URLs", () => {
  const passage = { ...source, label: null, content: source.excerpt, chunk_index: 0, is_current_generation: false };
  expect(parsePassage(passage, source.chunk_id).is_current_generation).toBe(false);
  expect(() => parsePassage(passage, "foreign")).toThrow();
  expect(() => parsePassage({ ...passage, content: "wrong" }, source.chunk_id)).toThrow();
  expect(passageHref("a/b", "c?d")).toBe("/dashboard/playground/a%2Fb/passages/c%3Fd");
  expect(safeSourceUri("javascript:alert(1)")).toBeNull();
  expect(safeSourceUri("https://user:secret@example.test/")).toBeNull();
  expect(safeSourceUri("https://example.test/source")).toBe("https://example.test/source");
});

test("server forwarding derives trusted identity, disables cache, validates returned query", async () => {
  process.env.BACKEND_INTERNAL_SECRET = "fixture-only";
  globalThis.fetch = async (url, options) => {
    expect(String(url)).toEndWith("/api/projects/p/query");
    expect(options.headers["X-User-Id"]).toBe("u");
    expect(options.headers["X-Organization-Id"]).toBe("o");
    expect(options.headers["X-Internal-Secret"]).toBe("fixture-only");
    expect(options.cache).toBe("no-store");
    expect(options.signal).toBeInstanceOf(AbortSignal);
    expect(JSON.parse(options.body)).toEqual({ message: "question", mode: "vector" });
    return Response.json(result);
  };
  expect(await queryProject("p", { message: "question", mode: "vector" })).toEqual(result);
});

test("action returns actual result without redirect; retains safe failure diagnostics", async () => {
  const form = new FormData();
  form.set("project_id", "p"); form.set("message", "question"); form.set("mode", "vector");
  globalThis.fetch = async () => Response.json(result);
  expect((await queryProjectAction({}, form)).result.answer).toBe(result.answer);
  globalThis.fetch = async () => Response.json({ error: "graph partial", code: "graph_partial" }, { status: 409 });
  expect(await queryProjectAction({}, form)).toEqual({ error: "graph partial", code: "graph_partial" });
  globalThis.fetch = async () => { throw new Error("secret driver connection details"); };
  expect((await queryProjectAction({}, form)).error).not.toContain("secret driver");
  globalThis.fetch = async () => Response.json({ answer: "Malformed success" });
  expect((await queryProjectAction({}, form)).result).toBeUndefined();
  form.set("message", "界".repeat(342));
  expect((await queryProjectAction({}, form)).error).toContain("1,024-byte");
});

test("passage and generic backend errors preserve HTTP failure without raw HTML leakage", async () => {
  globalThis.fetch = async () => Response.json({ error: "Source passage not found", code: "source_not_found" }, { status: 404 });
  await expect(sourcePassage("p", "foreign")).rejects.toBeInstanceOf(BackendError);
  globalThis.fetch = async () => new Response("<html>private proxy details</html>", { status: 502 });
  await expect(backendRequest("/test")).rejects.toThrow("Backend request failed: 502");
});

test("malformed corpus/document lists fail safely instead of reaching render", async () => {
  globalThis.fetch = async () => Response.json({ items: "not an array" });
  await expect(listProjects()).rejects.toThrow("Invalid corpus response");
  globalThis.fetch = async () => Response.json({ items: [{ id: "d", project_id: "p", file_name: "case", readiness: {} }] });
  await expect(listDocuments("p")).rejects.toThrow("Invalid document readiness response");
});
