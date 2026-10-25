import { getDashboardContext } from "@/lib/dashboard-context";
import { parsePassage, parseQueryResult, parseReadiness, type Readiness, type RetrievalMode } from "@/lib/rag-contract";

const backendUrl = process.env.BACKEND_URL || "http://localhost:5000";

type BackendOptions = {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: FormData | Record<string, unknown>;
  responseType?: "json" | "text";
  timeoutMs?: number;
};

export class BackendError extends Error {
  constructor(message: string, public status: number, public code?: string) {
    super(message);
  }
}

export async function backendRequest<T>(path: string, options: BackendOptions = {}): Promise<T> {
  const { session, organization, role } = await getDashboardContext();
  const isFormData = options.body instanceof FormData;
  let body: BodyInit | undefined;
  if (options.body instanceof FormData) {
    body = options.body;
  } else if (options.body) {
    body = JSON.stringify(options.body);
  }
  const response = await fetch(`${backendUrl}${path}`, {
    method: options.method || "GET",
    headers: {
      "X-Internal-Secret": process.env.BACKEND_INTERNAL_SECRET || "",
      "X-User-Id": session.user.id,
      "X-Organization-Id": organization.id,
      "X-User-Role": role,
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
    },
    body,
    cache: "no-store",
    signal: AbortSignal.timeout(options.timeoutMs ?? 30_000),
  });

  if (!response.ok && response.status !== 207) {
    const payload = await response.json().catch(() => null);
    throw new BackendError(typeof payload?.error === "string" ? payload.error : `Backend request failed: ${response.status}`, response.status, typeof payload?.code === "string" ? payload.code : undefined);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  if (options.responseType === "text") {
    return response.text() as Promise<T>;
  }

  return response.json() as Promise<T>;
}

export type Project = {
  id: string;
  name: string;
  slug: string;
  description?: string | null;
  default_query_mode: string;
  embedding_provider: string;
  embedding_model: string;
  default_llm_credential_id?: string | null;
  default_embedding_credential_id?: string | null;
  corpus_source: "private" | "legal";
  read_only: boolean;
  is_shared_reference: boolean;
};

export type Credential = {
  id: string;
  name: string;
  provider: string;
  credential_type: string;
  default_model?: string | null;
  default_embedding_model?: string | null;
  api_key_hint?: string;
  status: string;
};

export type Document = {
  id: string;
  project_id: string;
  file_name: string;
  status: string;
  created_at: number;
  updated_at: number;
  readiness?: { state: string; capabilities: Readiness["capabilities"] };
};

export type DataSource = {
  id: string;
  name: string;
  source_type: string;
  project_id?: string;
  ingestion_status?: string;
  processed_count?: number;
  completed_count?: number;
  failed_count?: number;
  last_source_id?: string | null;
  last_error?: string | null;
};

export async function listProjects() {
  const result = await backendRequest<{ items: Project[] }>("/api/projects");
  if (!Array.isArray(result?.items) || !result.items.every((item) => item && typeof item.id === "string" && typeof item.name === "string"
    && typeof item.read_only === "boolean" && typeof item.is_shared_reference === "boolean"
    && ((item.corpus_source === "legal" && item.read_only) || (item.corpus_source === "private" && !item.read_only && !item.is_shared_reference)))) {
    throw new Error("Invalid corpus response");
  }
  return result;
}

export async function listCredentials() {
  return backendRequest<{ items: Credential[] }>("/api/credentials");
}

export async function listDataSources() {
  return backendRequest<{ items: DataSource[] }>("/api/data-sources");
}

export async function createProject(payload: {
  name: string;
  slug: string;
  description: string;
  embedding_provider: string;
  embedding_model: string;
  default_llm_credential_id?: string;
  default_embedding_credential_id?: string;
  corpus_source: "private" | "legal";
}) {
  return backendRequest<Project>("/api/projects", { method: "POST", body: payload });
}

export async function createDataSource(payload: Record<string, string | boolean | undefined>) {
  return backendRequest<DataSource>("/api/data-sources", { method: "POST", body: payload });
}

export async function deleteProject(projectId: string) {
  return backendRequest<void>(`/api/projects/${projectId}`, { method: "DELETE" });
}

export async function listDocuments(projectId: string) {
  const result = await backendRequest<{ items: Document[] }>(`/api/projects/${encodeURIComponent(projectId)}/documents`, { timeoutMs: 120_000 });
  if (!Array.isArray(result?.items) || !result.items.every((item) => item && item.project_id === projectId
    && typeof item.id === "string" && typeof item.file_name === "string"
    && typeof item.readiness?.state === "string"
    && typeof item.readiness?.capabilities?.text === "boolean"
    && typeof item.readiness?.capabilities?.vector === "boolean"
    && typeof item.readiness?.capabilities?.graph === "boolean")) {
    throw new Error("Invalid document readiness response");
  }
  return result;
}

export async function createDocument(projectId: string, payload: FormData | { file_name: string }) {
  return backendRequest<{ items: { document_id: string; job_id: string; job: IngestionJob }[]; errors: { file_name: string; error: string }[] }>(`/api/projects/${encodeURIComponent(projectId)}/documents/upload`, { method: "POST", body: payload, timeoutMs: 120_000 });
}

export type IngestionJob = {
  document_id: string; project_id: string;
  state: "queued" | "active" | "completed" | "failed";
  stage: string; attempts: number; chunk_count: number; vector_count: number;
  error_code: string | null;
};

export async function listJobs(projectId: string) {
  const result = await backendRequest<{ items: IngestionJob[] }>(`/api/projects/${encodeURIComponent(projectId)}/jobs`);
  if (!Array.isArray(result.items) || !result.items.every((job) => job.project_id === projectId && typeof job.document_id === "string" && ["queued", "active", "completed", "failed"].includes(job.state) && typeof job.stage === "string" && Number.isSafeInteger(job.attempts) && Number.isSafeInteger(job.chunk_count) && Number.isSafeInteger(job.vector_count))) throw new Error("Invalid ingestion status");
  return result;
}

export async function deleteDocument(projectId: string, documentId: string) {
  return backendRequest<void>(`/api/projects/${projectId}/documents/${documentId}`, { method: "DELETE" });
}

export async function createCredential(payload: Record<string, string | undefined>) {
  return backendRequest<Credential>("/api/credentials", { method: "POST", body: payload });
}

export async function queryProject(projectId: string, payload: { message: string; mode: RetrievalMode }) {
  const response = await backendRequest<unknown>(`/api/projects/${encodeURIComponent(projectId)}/query`, { method: "POST", body: payload, timeoutMs: 300_000 });
  return parseQueryResult(response, projectId, payload.mode);
}

export async function indexingStatus(projectId: string) {
  return parseReadiness(await backendRequest<unknown>(`/api/projects/${encodeURIComponent(projectId)}/indexing/status`, { timeoutMs: 120_000 }), projectId);
}

export async function sourcePassage(projectId: string, chunkId: string) {
  return parsePassage(await backendRequest<unknown>(`/api/projects/${encodeURIComponent(projectId)}/passages/${encodeURIComponent(chunkId)}`), chunkId);
}

export async function graphStatus(projectId: string) {
  return backendRequest<{ exists: boolean; node_count: number; edge_count: number }>(`/api/projects/${projectId}/graph/status`);
}

export type GraphNode = {
  id: string;
  label: string;
};

export type GraphEdge = {
  source: string;
  target: string;
  label?: string | null;
};

export type ProjectGraph = {
  nodes: GraphNode[];
  edges: GraphEdge[];
};

export async function graphData(projectId: string) {
  return backendRequest<ProjectGraph>(`/api/projects/${projectId}/graph/data`);
}

export function graphHtmlUrl(projectId: string) {
  return `/dashboard/graph/${projectId}/html`;
}

export async function graphHtml(projectId: string) {
  return backendRequest<string>(`/api/projects/${projectId}/graph`, { responseType: "text" });
}
