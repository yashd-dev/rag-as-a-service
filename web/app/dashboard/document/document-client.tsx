"use client";

import { useRouter } from "next/navigation";
import { useActionState, useState } from "react";
import type { FormEvent } from "react";
import { useFormStatus } from "react-dom";
import { ArrowLeft, Check, ChevronDown, Code2, Database, Plus, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { DataSource, Document, Project } from "@/lib/backend";

const corpusJson = `{
  "corpusKey": "supreme_court",
  "name": "Supreme Court",
  "description": "Supreme Court Documents",
  "documentsAreQuestions": false,
  "filterAttributes": [
    {
      "name": "lang",
      "level": "part",
      "type": "text",
      "description": "Detected language, as an ISO 639-3 code.",
      "indexed": true
    },
    {
      "name": "is_title",
      "level": "part",
      "type": "boolean",
      "description": "True if the text is a title.",
      "indexed": true
    }
  ]
}`;

const embeddingModels = [
  {
    provider: "huggingface",
    model: "google/embeddinggemma-300m",
    label: "embeddinggemma-300m",
    description: "Supported backend embedding baseline. Effective Ollama model and revision are verified during indexing and querying.",
  },
] as const;

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="overflow-hidden rounded-xl border bg-background">
      <div className="flex items-center gap-2 border-b px-4 py-3 font-medium tracking-tight">
        <ChevronDown className="size-4" />
        {title}
      </div>
      <div className="p-4 md:p-6">{children}</div>
    </section>
  );
}

function Field({ label, helper, children }: { label: string; helper?: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-2">
      <span className="text-sm font-medium tracking-tight">{label}</span>
      {helper ? <span className="text-sm text-muted-foreground">{helper}</span> : null}
      {children}
    </label>
  );
}

type DocumentClientProps = {
  projects: Project[];
  dataSources: DataSource[];
  documentsByProject: Record<string, Document[] | null>;
  createProjectAction: (_state: { error?: string } | undefined, formData: FormData) => Promise<{ error?: string } | undefined>;
  deleteProjectAction: (formData: FormData) => void;
  deleteDocumentAction: (formData: FormData) => void;
};

function CreateCorpusButton() {
  const { pending } = useFormStatus();
  return (
    <button type="submit" disabled={pending} className="h-11 rounded-lg bg-primary px-5 text-sm font-normal text-primary-foreground transition-colors hover:bg-primary/80 disabled:pointer-events-none disabled:opacity-70">
      {pending ? "Creating..." : "Create corpus"}
    </button>
  );
}

export function DocumentClient({ projects, dataSources, documentsByProject, createProjectAction, deleteProjectAction, deleteDocumentAction }: DocumentClientProps) {
  const [mode, setMode] = useState<"empty" | "create">(projects.length ? "empty" : "empty");
  const [jsonOpen, setJsonOpen] = useState(false);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadFiles, setUploadFiles] = useState<string[]>([]);
  const [createState, formAction] = useActionState(createProjectAction, undefined);
  const router = useRouter();
  const selectedProject = projects.find((project) => project.id === selectedProjectId) || null;

  async function handleDocumentUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedProject) {
      return;
    }
    const form = event.currentTarget;
    const input = form.elements.namedItem("file") as HTMLInputElement | null;
    const files = Array.from(input?.files || []);
    if (!files.length) {
      setUploadError("Choose at least one file to upload.");
      return;
    }
    setUploading(true);
    setUploadError(null);
    setUploadFiles(files.map((file) => file.name));
    const body = new FormData();
    for (const file of files) {
      body.append("file", file);
    }
    try {
      const response = await fetch(`/api/projects/${selectedProject.id}/documents/upload`, {
        method: "POST",
        body,
      });
      const payload = await response.json().catch(() => null);
      if (!response.ok && response.status !== 207) {
        throw new Error(payload?.error || `Upload failed with status ${response.status}`);
      }
      if (payload?.errors?.length) {
        throw new Error(payload.errors.map((item: { file_name: string; error: string }) => `${item.file_name}: ${item.error}`).join("; "));
      }
      form.reset();
      router.refresh();
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : "Could not upload document.");
    } finally {
      setUploading(false);
    }
  }

  if (mode === "empty" && selectedProject) {
    const documents = documentsByProject[selectedProject.id] || [];
    const projectSources = dataSources.filter((source) => source.source_type === "turso_ocr" && source.project_id === selectedProject.id);
    return (
      <div className="flex min-h-[calc(100svh-4rem)] flex-col">
        <div className="flex h-16 items-center justify-between border-b px-4 md:px-6">
          <div className="min-w-0">
            <button type="button" onClick={() => setSelectedProjectId(null)} className="text-sm text-muted-foreground hover:text-foreground">Documents / Corpus</button>
            <h1 className="truncate text-2xl font-semibold tracking-tight">{selectedProject.name}</h1>
          </div>
          <Button type="button" onClick={() => setMode("create")} className="h-11 gap-2 px-4 font-normal">
            <Plus className="size-4" />
            Create corpus
          </Button>
        </div>

        <div className="grid gap-5 p-4 md:p-6">
          <section className="rounded-xl border bg-background p-4 md:p-5">
            <h2 className="font-medium tracking-tight">Upload document</h2>
            <p className="mt-1 text-sm text-muted-foreground">Upload one or more text files or PDFs with embedded text. Upload stages canonical text and chunks only; vector and graph indexing require the documented backend batch commands. Scanned PDFs need usable OCR text first.</p>
            <form onSubmit={handleDocumentUpload} className="mt-4 flex flex-col gap-3">
              <input type="hidden" name="project_id" value={selectedProject.id} />
              <div className="flex flex-col gap-3 sm:flex-row">
                <input name="file" type="file" aria-label="Documents to upload" multiple disabled={uploading} className="h-11 flex-1 rounded-lg border bg-background px-3 py-2 text-sm outline-none file:mr-3 file:rounded-md file:border-0 file:bg-secondary file:px-3 file:py-1.5 file:text-sm focus:ring-2 focus:ring-ring disabled:opacity-60" />
                <button type="submit" disabled={uploading} className="h-11 rounded-lg bg-primary px-5 text-sm font-normal text-primary-foreground transition-colors hover:bg-primary/80 disabled:pointer-events-none disabled:opacity-70">
                  {uploading ? "Processing..." : "Upload and process"}
                </button>
              </div>
              {uploading ? (
                <div className="rounded-lg border border-primary/20 bg-primary/5 p-3 text-sm text-muted-foreground">
                    Staging text for {uploadFiles.length} file{uploadFiles.length === 1 ? "" : "s"}: {uploadFiles.join(", ")}. Retrieval readiness is verified separately.
                </div>
              ) : null}
              {uploadError ? <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{uploadError}</div> : null}
            </form>
          </section>

          {projectSources.length ? (
            <section className="overflow-hidden rounded-xl border bg-background">
              <div className="grid grid-cols-[1fr_140px_120px_120px_120px] gap-3 border-b bg-secondary px-4 py-3 text-sm font-medium">
                <span>OCR source</span>
                <span>Status</span>
                <span>Processed</span>
                <span>Completed</span>
                <span>Failed</span>
              </div>
              {projectSources.map((source) => (
                <div key={source.id} className="grid grid-cols-[1fr_140px_120px_120px_120px] items-center gap-3 border-b px-4 py-3 text-sm last:border-b-0 hover:bg-card">
                  <div className="min-w-0">
                    <p className="truncate font-medium tracking-tight">{source.name}</p>
                    <p className="truncate text-xs text-muted-foreground">{source.last_error || source.last_source_id || source.id}</p>
                  </div>
                  <span className="w-fit rounded-full bg-secondary px-2.5 py-1 text-xs text-muted-foreground">{source.ingestion_status || "pending"}</span>
                  <span className="text-muted-foreground">{source.processed_count ?? 0}</span>
                  <span className="text-muted-foreground">{source.completed_count ?? 0}</span>
                  <span className="text-muted-foreground">{source.failed_count ?? 0}</span>
                </div>
              ))}
            </section>
          ) : null}

          {documentsByProject[selectedProject.id] === null ? <p role="alert" className="rounded-xl border p-4 text-sm">Document readiness unavailable. Reload to retry.</p> : null}
          <section className="overflow-x-auto rounded-xl border bg-background">
            <div className="grid grid-cols-[1fr_140px_160px_96px] gap-3 border-b bg-secondary px-4 py-3 text-sm font-medium">
              <span>Document</span>
              <span>Status</span>
              <span>Created</span>
              <span />
            </div>
            {documents.length ? documents.map((document) => (
              <div key={document.id} className="grid grid-cols-[1fr_140px_160px_96px] items-center gap-3 border-b px-4 py-3 text-sm last:border-b-0 hover:bg-card">
                <div className="min-w-0">
                  <p className="truncate font-medium tracking-tight">{document.file_name}</p>
                  <p className="truncate text-xs text-muted-foreground">{document.id}</p>
                </div>
                <span className="text-xs text-muted-foreground">{document.readiness?.state || "unverified"}<span className="mt-1 block">Text {document.readiness?.capabilities.text ? "✓" : "—"} · Vector {document.readiness?.capabilities.vector ? "✓" : "—"} · Graph {document.readiness?.capabilities.graph ? "✓" : "—"}</span></span>
                <span className="text-muted-foreground">{new Date(document.created_at).toLocaleDateString()}</span>
                <form action={deleteDocumentAction}>
                  <input type="hidden" name="project_id" value={selectedProject.id} />
                  <input type="hidden" name="document_id" value={document.id} />
                  <button type="submit" className="h-9 rounded-lg border px-3 text-sm text-destructive hover:bg-destructive/10">Remove</button>
                </form>
              </div>
            )) : (
              <div className="p-8 text-center text-sm text-muted-foreground">No documents added to this corpus yet.</div>
            )}
          </section>
        </div>
      </div>
    );
  }

  if (mode === "empty" && !projects.length) {
    return (
      <div className="flex min-h-[calc(100svh-4rem)] flex-col">
        <div className="flex h-16 items-center justify-between border-b px-4 md:px-6">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span>Documents</span>
            <span>/</span>
            <span className="text-foreground">Corpus</span>
          </div>
          <Button type="button" onClick={() => setMode("create")} className="h-11 gap-2 px-4 font-normal">
            <Plus className="size-4" />
            Create corpus
          </Button>
        </div>

        <div className="grid flex-1 place-items-center p-6">
          <div className="flex max-w-2xl flex-col items-center text-center">
            <div className="mb-8 grid size-16 place-items-center text-foreground">
              <Database className="size-12" strokeWidth={1.5} />
            </div>
            <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">A corpus is required before adding documents</h1>
            <p className="mt-4 max-w-xl text-base text-muted-foreground">
              Create a corpus to organize documents, configure retrieval metadata, and ground your assistants in your data.
            </p>
            <div className="mt-10 grid w-full gap-4">
              <button type="button" onClick={() => setMode("create")} className="rounded-xl border bg-card p-5 text-left transition-colors hover:bg-(--card-hover)">
                <h2 className="font-medium tracking-tight text-primary">Create your own corpus</h2>
                <p className="mt-2 text-sm text-muted-foreground">Fill your corpus with PDFs, text documents, or an OCR Turso database.</p>
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (mode === "empty") {
    return (
      <div className="flex min-h-[calc(100svh-4rem)] flex-col">
        <div className="flex h-16 items-center justify-between border-b px-4 md:px-6">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span>Documents</span>
            <span>/</span>
            <span className="text-foreground">Corpus</span>
          </div>
          <Button type="button" onClick={() => setMode("create")} className="h-11 gap-2 px-4 font-normal">
            <Plus className="size-4" />
            Create corpus
          </Button>
        </div>
        <div className="p-4 md:p-6">
          <div className="overflow-x-auto rounded-xl border bg-background">
            <div className="grid grid-cols-[1fr_240px_160px_120px_96px] gap-3 border-b bg-secondary px-4 py-3 text-sm font-medium">
              <span>Name</span>
              <span>Embedding</span>
              <span>Mode</span>
              <span>Status</span>
              <span />
            </div>
            {projects.map((project) => (
              <div key={project.id} className="grid grid-cols-[1fr_240px_160px_120px_96px] items-center gap-3 border-b px-4 py-3 text-sm last:border-b-0 hover:bg-card">
                <button type="button" onClick={() => setSelectedProjectId(project.id)} className="min-w-0 text-left">
                  <p className="truncate font-medium tracking-tight text-primary">{project.name}</p>
                  <p className="truncate text-xs text-muted-foreground">{project.slug} · {(documentsByProject[project.id] || []).length} documents</p>
                </button>
                <span className="truncate text-muted-foreground">{project.embedding_model || "Not configured"}</span>
                <span className="text-muted-foreground">{project.default_query_mode}</span>
                <span className="w-fit rounded-full bg-secondary px-2.5 py-1 text-xs text-muted-foreground">{documentsByProject[project.id] === null ? "Unavailable" : !(documentsByProject[project.id]?.length) ? "No documents" : documentsByProject[project.id]?.every((doc) => doc.readiness?.capabilities.graph) ? "Graph available" : documentsByProject[project.id]?.every((doc) => doc.readiness?.capabilities.vector) ? "Vector available" : documentsByProject[project.id]?.every((doc) => doc.readiness?.capabilities.text) ? "Text only" : "Partial / pending"}</span>
                <form action={deleteProjectAction}>
                  <input type="hidden" name="project_id" value={project.id} />
                  <button type="submit" className="h-9 rounded-lg border px-3 text-sm text-destructive hover:bg-destructive/10">
                    Delete
                  </button>
                </form>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="relative min-h-[calc(100svh-4rem)] overflow-hidden bg-background">
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-7 p-4 md:p-8">
        <button type="button" onClick={() => setMode("empty")} className="flex w-fit items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-4" />
          Back
        </button>

        <form action={formAction} className="flex flex-col gap-5">
          <h1 className="text-2xl font-semibold tracking-tight">What do you want to name this corpus?</h1>
          <div className="grid max-w-2xl gap-5">
            <Field label="Name (required)" helper="Enter a name up to 50 characters long.">
              <input name="name" defaultValue="Supreme Court" className="h-11 rounded-lg border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring" />
            </Field>
            <Field label="Key (required)" helper="Enter a key up to 50 characters long. This will be used to uniquely identify the corpus.">
              <input name="slug" defaultValue="supreme_court" className="h-11 rounded-lg border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring" />
            </Field>
          </div>
        

        <div className="flex flex-col gap-5">
          <h2 className="text-2xl font-semibold tracking-tight">Corpus configuration</h2>
          <Field label="Description">
            <textarea name="description" defaultValue="Supreme Court Documents" className="min-h-28 rounded-lg border bg-background p-3 text-sm outline-none focus:ring-2 focus:ring-ring" />
          </Field>

          <Section title="Source database">
            <p className="text-sm text-muted-foreground">
              Optional: attach a Turso database that already contains OCR text. Saving this configuration does not start ingestion; use the documented backend batch commands to stage and index it.
            </p>
            <div className="mt-6 grid gap-4">
              <Field label="Turso database URL" helper="Example: libsql://ocr-content-org.aws-ap-south-1.turso.io">
                <input name="source_turso_url" placeholder="libsql://..." className="h-11 rounded-lg border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring" />
              </Field>
              <Field label="Turso auth token" helper="Stored encrypted by the backend. Leave blank if you are not attaching an OCR database yet.">
                <input name="source_turso_token" type="password" autoComplete="off" className="h-11 rounded-lg border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring" />
              </Field>
              <Field label="Content table" helper="The dataset-api schema stores PDF OCR rows in the pdfs table.">
                <input name="source_turso_table" defaultValue="pdfs" className="h-11 rounded-lg border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring" />
              </Field>
              <div className="grid gap-4 md:grid-cols-2">
                <Field label="ID column">
                  <input name="source_turso_id_column" defaultValue="path" className="h-11 rounded-lg border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring" />
                </Field>
                <Field label="Text column">
                  <input name="source_turso_text_column" defaultValue="ocr_text" className="h-11 rounded-lg border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring" />
                </Field>
              </div>
              <div className="grid gap-4 md:grid-cols-3">
                <Field label="Status column">
                  <input name="source_turso_status_column" defaultValue="ocr_status" className="h-11 rounded-lg border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring" />
                </Field>
                <Field label="Ready value">
                  <input name="source_turso_status_value" defaultValue="done" className="h-11 rounded-lg border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring" />
                </Field>
                <Field label="URL column">
                  <input name="source_turso_url_column" defaultValue="url" className="h-11 rounded-lg border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring" />
                </Field>
              </div>
            </div>
          </Section>

          <Section title="Embedding model">
            <p className="text-sm text-muted-foreground">Supported project model metadata. Effective model, digest and dimensions are verified by the backend; alternate model execution is not available here.</p>
            <input type="hidden" name="embedding_provider" value="huggingface" />
            <div className="mt-6 grid gap-3">
              {embeddingModels.map((item, index) => (
                <label key={item.model} className="flex items-start gap-4 rounded-xl border bg-card p-4 hover:bg-(--card-hover)">
                  <input type="radio" name="embedding_model" value={item.model} defaultChecked={index === 0} className="mt-1 size-4" />
                  <span>
                    <span className="block text-sm font-medium tracking-tight">{item.label}</span>
                    <span className="mt-1 block text-xs text-muted-foreground">{item.model}</span>
                    <span className="mt-2 block text-sm text-muted-foreground">{item.description}</span>
                  </span>
                </label>
              ))}
            </div>
          </Section>

        </div>

        {createState?.error ? <p className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{createState.error}</p> : null}

        <div className="flex items-center justify-between pb-10">
          <CreateCorpusButton />
          <button type="button" onClick={() => setJsonOpen(true)} className="flex items-center gap-2 text-sm font-medium text-primary">
            <Code2 className="size-4" />
            Edit JSON
          </button>
        </div>
        </form>
      </div>

      {jsonOpen ? (
        <div className="absolute inset-0 z-40 flex bg-foreground/45">
          <button type="button" aria-label="Close JSON editor" className="flex-1" onClick={() => setJsonOpen(false)} />
          <aside className="flex w-full max-w-2xl flex-col bg-background shadow-xl">
            <div className="flex h-16 items-center justify-between border-b px-6">
              <div className="flex items-center gap-2 font-semibold tracking-tight"><Code2 className="size-4 text-primary" />Edit corpus JSON</div>
              <button type="button" onClick={() => setJsonOpen(false)}><X className="size-4" /></button>
            </div>
            <div className="flex-1 p-6">
              <h3 className="font-medium tracking-tight">Corpus JSON</h3>
              <p className="mt-2 text-sm text-muted-foreground">Edit the corpus configuration as JSON.</p>
              <textarea defaultValue={corpusJson} className="mt-4 h-80 w-full rounded-lg border bg-background p-4 font-mono text-sm outline-none focus:ring-2 focus:ring-ring" />
            </div>
            <div className="flex items-center justify-between border-t p-6">
              <Button type="button" variant="outline" onClick={() => setJsonOpen(false)} className="h-11 px-5 font-normal">Cancel</Button>
              <Button type="button" onClick={() => setJsonOpen(false)} className="h-11 gap-2 px-5 font-normal"><Check className="size-4" />Apply changes</Button>
            </div>
          </aside>
        </div>
      ) : null}
    </div>
  );
}
