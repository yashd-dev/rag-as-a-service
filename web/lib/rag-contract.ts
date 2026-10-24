export type RetrievalMode = "vector" | "graph" | "hybrid";

export type Readiness = {
  project_id: string;
  state: string;
  capabilities: { text: boolean; vector: boolean; graph: boolean };
  counts: Record<string, number>;
  verified_at: number;
  failures: { stage: string; code: string; retryable: boolean }[];
};

export type Source = {
  citation_id: string;
  label: string | null;
  chunk_id: string;
  document_id: string;
  generation_id: string;
  file_name: string | null;
  excerpt: string;
  content_hash: string;
  start_char: number;
  end_char: number;
  pages: { page: number; start: number; end: number }[];
  source_uri: string | null;
  score: number | null;
  fusion_score: number | null;
  retrieval_methods: string[];
  retrieval_path: unknown[];
};

export type Passage = Source & {
  content: string;
  chunk_index: number;
  is_current_generation: boolean;
};

export type QueryResult = {
  project_id: string;
  query_run_id: string;
  mode: RetrievalMode;
  status: "answered" | "insufficient_evidence";
  answer: string;
  sources: Source[];
  citation_candidates: Source[];
  used_citation_ids: string[];
  generation: { provider: string | null; model: string | null; fallback: boolean; called: boolean; fallback_reason?: string };
  vector_generation: string;
  graph_generation: string | null;
  retrieval_diagnostics: {
    path: string;
    ranking: string;
    candidate_count: number;
    context_count: number;
    graph_added: number;
    retrieval_ms: number;
    generation_ms: number;
  };
};

export type QueryState = { result?: QueryResult; error?: string; code?: string };

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
const text = (value: unknown): value is string => typeof value === "string";
const numeric = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value) && value >= 0;
const strings = (value: unknown): value is string[] => Array.isArray(value) && value.every(text);

function source(value: unknown): value is Source {
  return record(value)
    && ["citation_id", "chunk_id", "document_id", "generation_id", "excerpt", "content_hash"].every((key) => text(value[key]))
    && (value.label === null || text(value.label)) && (value.file_name === null || text(value.file_name))
    && numeric(value.start_char) && numeric(value.end_char) && value.end_char > value.start_char
    && Array.isArray(value.pages) && value.pages.every((page) => record(page) && numeric(page.page) && numeric(page.start) && numeric(page.end))
    && (value.source_uri === null || text(value.source_uri))
    && (value.score === null || numeric(value.score)) && (value.fusion_score === null || numeric(value.fusion_score))
    && strings(value.retrieval_methods) && Array.isArray(value.retrieval_path);
}

export function parseReadiness(value: unknown, projectId?: string): Readiness {
  if (!record(value) || !text(value.project_id) || (projectId !== undefined && value.project_id !== projectId)
    || !text(value.state) || !record(value.capabilities)
    || !["text", "vector", "graph"].every((key) => typeof value.capabilities === "object" && typeof (value.capabilities as Record<string, unknown>)[key] === "boolean")
    || !record(value.counts) || !Object.values(value.counts).every(numeric) || !numeric(value.counts.total)
    || !numeric(value.verified_at)
    || (value.failures !== undefined && (!Array.isArray(value.failures)
      || !value.failures.every((failure) => record(failure) && text(failure.stage) && text(failure.code) && typeof failure.retryable === "boolean")))) {
    throw new Error("Invalid readiness response");
  }
  return { ...value, failures: value.failures ?? [] } as Readiness;
}

export function parseQueryResult(value: unknown, projectId: string, mode: RetrievalMode): QueryResult {
  if (!record(value) || value.project_id !== projectId || value.mode !== mode
    || !text(value.query_run_id) || !text(value.answer) || !["answered", "insufficient_evidence"].includes(String(value.status))
    || !Array.isArray(value.sources) || !value.sources.every(source)
    || !value.sources.every((item) => typeof item.label === "string" && /^S\d+$/.test(item.label))
    || !Array.isArray(value.citation_candidates) || !value.citation_candidates.every(source)
    || !strings(value.used_citation_ids) || value.used_citation_ids.length !== value.sources.length
    || !value.sources.every((item) => (value.used_citation_ids as string[]).includes(item.citation_id))
    || (value.status === "answered" && !value.sources.length)
    || (value.status === "insufficient_evidence" && value.sources.length !== 0)
    || !text(value.vector_generation) || !(value.graph_generation === null || text(value.graph_generation))
    || !record(value.generation) || !["provider", "model"].every((key) => (value.generation as Record<string, unknown>)[key] === null || text((value.generation as Record<string, unknown>)[key]))
    || typeof value.generation.called !== "boolean" || typeof value.generation.fallback !== "boolean"
    || !record(value.retrieval_diagnostics) || !text(value.retrieval_diagnostics.path) || !text(value.retrieval_diagnostics.ranking)
    || !["candidate_count", "context_count", "graph_added", "retrieval_ms", "generation_ms"].every((key) => numeric((value.retrieval_diagnostics as Record<string, unknown>)[key]))) {
    throw new Error("Invalid query response");
  }
  const result = value as QueryResult;
  const labels = new Set(result.sources.map((item) => item.label));
  const inline = new Set([...result.answer.matchAll(/\[(S[^\]]*)\]/g)].map((match) => match[1]));
  if (labels.size !== result.sources.length || inline.size !== labels.size
    || ![...inline].every((label) => labels.has(label))
    || new Set(result.used_citation_ids).size !== result.used_citation_ids.length) {
    throw new Error("Invalid query citations");
  }
  return result;
}

export function parsePassage(value: unknown, chunkId: string): Passage {
  if (!record(value) || !text(value.content) || value.content !== value.excerpt
    || !numeric(value.chunk_index) || typeof value.is_current_generation !== "boolean"
    || !source(value) || value.chunk_id !== chunkId) {
    throw new Error("Invalid passage response");
  }
  return value as Passage;
}

export function modeAvailable(readiness: Readiness | null, mode: RetrievalMode) {
  return !!readiness?.capabilities.vector && (mode === "vector" || readiness.capabilities.graph);
}

export function passageHref(projectId: string, chunkId: string) {
  return `/dashboard/playground/${encodeURIComponent(projectId)}/passages/${encodeURIComponent(chunkId)}`;
}

export function safeSourceUri(uri: string | null) {
  if (!uri) return null;
  try {
    const url = new URL(uri);
    return ["http:", "https:"].includes(url.protocol) && !url.username && !url.password ? url.href : null;
  } catch {
    return null;
  }
}
