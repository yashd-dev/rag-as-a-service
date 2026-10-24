"use server";

import { revalidatePath } from "next/cache";
import { redirect, unstable_rethrow } from "next/navigation";

import { BackendError, createCredential, createDataSource, createDocument, createProject, deleteDocument, deleteProject, queryProject } from "@/lib/backend";
import type { QueryState } from "@/lib/rag-contract";

export async function createProjectAction(_state: { error?: string } | undefined, formData: FormData) {
  try {
    console.log("createProjectAction", {
      slug: String(formData.get("slug") || "").trim(),
      embedding_model: String(formData.get("embedding_model") || "google/embeddinggemma-300m").trim(),
      has_turso_source: Boolean(String(formData.get("source_turso_url") || "").trim()),
    });
    const project = await createProject({
      name: String(formData.get("name") || "").trim(),
      slug: String(formData.get("slug") || "").trim(),
      description: String(formData.get("description") || "").trim(),
      embedding_provider: String(formData.get("embedding_provider") || "huggingface").trim(),
      embedding_model: String(formData.get("embedding_model") || "google/embeddinggemma-300m").trim(),
      default_llm_credential_id: String(formData.get("default_llm_credential_id") || "").trim() || undefined,
      default_embedding_credential_id: String(formData.get("default_embedding_credential_id") || "").trim() || undefined,
    });
    console.log("createProjectAction project created", { project_id: project.id, name: project.name });

    const tursoUrl = String(formData.get("source_turso_url") || "").trim();
    const tursoToken = String(formData.get("source_turso_token") || "").trim();
    if (tursoUrl || tursoToken) {
      if (!tursoUrl || !tursoToken) {
        return { error: "Both Turso database URL and auth token are required for a source database." };
      }
      console.log("createProjectAction creating turso data source", {
        project_id: project.id,
        table_name: String(formData.get("source_turso_table") || "pdfs").trim(),
        id_column: String(formData.get("source_turso_id_column") || "path").trim(),
        text_column: String(formData.get("source_turso_text_column") || "ocr_text").trim(),
        skip_graph_extraction: String(formData.get("source_skip_graph_extraction") || "false") === "true",
      });
      const source = await createDataSource({
        name: `${project.name} OCR Turso source`,
        source_type: "turso_ocr",
        turso_database_url: tursoUrl,
        turso_auth_token: tursoToken,
        table_name: String(formData.get("source_turso_table") || "pdfs").trim(),
        id_column: String(formData.get("source_turso_id_column") || "path").trim(),
        text_column: String(formData.get("source_turso_text_column") || "ocr_text").trim(),
        status_column: String(formData.get("source_turso_status_column") || "ocr_status").trim(),
        status_value: String(formData.get("source_turso_status_value") || "done").trim(),
        url_column: String(formData.get("source_turso_url_column") || "url").trim(),
        project_id: project.id,
        skip_graph_extraction: String(formData.get("source_skip_graph_extraction") || "false") === "true",
      });
      console.log("createProjectAction turso data source created", {
        project_id: project.id,
        source_id: source.id,
        ingestion_status: source.ingestion_status,
      });
    }
  } catch (error) {
    return { error: error instanceof Error ? error.message : "Could not create corpus." };
  }

  revalidatePath("/dashboard/document");
  redirect("/dashboard/document");
}

export async function createCredentialAction(formData: FormData) {
  await createCredential({
    name: String(formData.get("name") || "").trim(),
    provider: String(formData.get("provider") || "openai").trim(),
    credential_type: String(formData.get("credential_type") || "llm").trim(),
    api_key: String(formData.get("api_key") || "").trim(),
    base_url: String(formData.get("base_url") || "").trim() || undefined,
    default_model: String(formData.get("default_model") || "").trim() || undefined,
    default_embedding_model: String(formData.get("default_embedding_model") || "").trim() || undefined,
  });

  revalidatePath("/dashboard/llm");
  redirect("/dashboard/llm");
}

export async function queryProjectAction(_state: QueryState, formData: FormData): Promise<QueryState> {
  const projectId = String(formData.get("project_id") || "");
  const message = String(formData.get("message") || "").trim();
  const mode = String(formData.get("mode") || "vector");
  if (!projectId || !message) {
    return { error: "Choose a corpus and enter a question." };
  }
  if (mode !== "vector" && mode !== "graph" && mode !== "hybrid") return { error: "Unsupported retrieval mode." };
  if (new TextEncoder().encode(message).length > 1024) return { error: "Question exceeds the 1,024-byte limit." };
  try {
    return { result: await queryProject(projectId, { message, mode }) };
  } catch (error) {
    unstable_rethrow(error);
    return error instanceof BackendError
      ? { error: error.message, code: error.code }
      : { error: "Query could not finish. The backend may be unavailable, timed out, or returned an invalid response. Your question is preserved; retry when ready." };
  }
}

export async function deleteProjectAction(formData: FormData) {
  const projectId = String(formData.get("project_id") || "");
  if (projectId) {
    await deleteProject(projectId);
  }

  revalidatePath("/dashboard/document");
  redirect("/dashboard/document");
}

export async function createDocumentAction(formData: FormData) {
  const projectId = String(formData.get("project_id") || "").trim();
  const files = formData.getAll("file").filter((file): file is File => file instanceof File && file.size > 0);
  if (projectId && files.length) {
    const upload = new FormData();
    for (const file of files) {
      upload.append("file", file);
    }
    try {
      const result = await createDocument(projectId, upload);
      if ("errors" in result && result.errors.length) {
        throw new Error(result.errors.map((item) => `${item.file_name}: ${item.error}`).join("; "));
      }
    } catch (error) {
      throw new Error(error instanceof Error ? error.message : "Could not upload document");
    }
  }

  revalidatePath("/dashboard/document");
  redirect("/dashboard/document");
}

export async function deleteDocumentAction(formData: FormData) {
  const projectId = String(formData.get("project_id") || "").trim();
  const documentId = String(formData.get("document_id") || "").trim();
  if (projectId && documentId) {
    await deleteDocument(projectId, documentId);
  }

  revalidatePath("/dashboard/document");
  redirect("/dashboard/document");
}
