"use client";

import Link from "next/link";
import { useActionState, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import type { Project } from "@/lib/backend";
import { modeAvailable, parseReadiness, passageHref, type QueryState, type Readiness, type RetrievalMode, type Source } from "@/lib/rag-contract";

type Props = {
  projects: Project[];
  queryProjectAction: (state: QueryState, formData: FormData) => Promise<QueryState>;
  error?: string;
};

function SourceCard({ source, projectId }: { source: Source; projectId: string }) {
  return (
    <li className="min-w-0 rounded-xl border bg-card p-4">
      <a href={passageHref(projectId, source.chunk_id)} target="_blank" rel="noopener noreferrer" className="break-words font-medium text-primary underline underline-offset-4">
        [{source.label}] {source.file_name || source.document_id} — open passage
      </a>
      <p className="mt-2 text-xs text-muted-foreground">
        Characters {source.start_char}–{source.end_char}
        {source.pages.length ? ` · Pages ${source.pages.map((page) => page.page).join(", ")}` : " · Page numbers unavailable"}
      </p>
      <blockquote className="mt-3 whitespace-pre-wrap break-words border-l-2 pl-3 text-sm leading-relaxed">{source.excerpt}</blockquote>
      <p className="mt-3 text-xs text-muted-foreground">
        {source.retrieval_methods.join(", ")}
        {source.score !== null ? ` · Cosine ${source.score.toFixed(4)}` : ""}
        {source.fusion_score !== null ? ` · Fusion ${source.fusion_score.toFixed(4)}` : ""}
      </p>
      {source.retrieval_path.length ? <details className="mt-2 text-xs"><summary className="cursor-pointer">Graph evidence path</summary><pre className="mt-2 overflow-auto whitespace-pre-wrap break-all">{JSON.stringify(source.retrieval_path, null, 2)}</pre></details> : null}
    </li>
  );
}

function CorpusPlayground({ projects, project, queryProjectAction, onProjectChange }: Props & { project: Project; onProjectChange: (id: string) => void }) {
  const [state, formAction, pending] = useActionState(queryProjectAction, {});
  const [message, setMessage] = useState("");
  const [submittedQuestion, setSubmittedQuestion] = useState("");
  const [mode, setMode] = useState<RetrievalMode>("vector");
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [checking, setChecking] = useState(true);
  const [refresh, setRefresh] = useState(0);
  const questionBytes = new TextEncoder().encode(message.trim()).length;
  const result = state.result;

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 125_000);
    async function load() {
      try {
        const response = await fetch(`/api/projects/${encodeURIComponent(project.id)}/indexing/status`, { cache: "no-store", signal: controller.signal });
        const payload: unknown = await response.json();
        if (!response.ok) throw new Error("Readiness unavailable. Check your session/backend and retry.");
        const status = parseReadiness(payload, project.id);
        if (active) setReadiness(status);
      } catch {
        if (active) setStatusError(controller.signal.aborted ? "Readiness request timed out. Retry when the backend is reachable." : "Could not verify readiness. Check your session/backend and retry.");
      } finally {
        clearTimeout(timeout);
        if (active) setChecking(false);
      }
    }
    void load();
    return () => { active = false; controller.abort(); clearTimeout(timeout); };
  }, [project.id, refresh]);

  return (
    <div className="mx-auto grid w-full max-w-6xl gap-6 p-4 md:p-6">
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="grid gap-2 text-sm font-medium">Corpus
          <select value={project.id} disabled={pending} onChange={(event) => onProjectChange(event.target.value)} className="h-11 min-w-0 rounded-lg border bg-background px-3 focus-visible:ring-2 focus-visible:ring-ring">
            {projects.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
        </label>
        <label className="grid gap-2 text-sm font-medium">Retrieval mode
          <select value={mode} disabled={pending || checking} onChange={(event) => setMode(event.target.value as RetrievalMode)} className="h-11 rounded-lg border bg-background px-3 focus-visible:ring-2 focus-visible:ring-ring">
            {(["vector", "graph", "hybrid"] as const).map((item) => <option key={item} value={item} disabled={!modeAvailable(readiness, item)}>{item}{!checking && !modeAvailable(readiness, item) ? " — unavailable" : ""}</option>)}
          </select>
        </label>
      </div>

      <section aria-label="Index readiness" aria-busy={checking} className="rounded-xl border bg-card p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-medium">Index readiness</h2>
          <Button type="button" variant="outline" disabled={checking || pending} onClick={() => { setReadiness(null); setStatusError(null); setChecking(true); setRefresh((value) => value + 1); }}>Refresh readiness</Button>
        </div>
        <div role="status" className="mt-3 text-sm">
          {checking ? "Checking source and index integrity… This can take up to two minutes." : statusError || (readiness ? `State: ${readiness.state}` : "Readiness unknown")}
        </div>
        {readiness ? <>
          <p className="mt-2 text-sm">Text: {readiness.capabilities.text ? "available" : "unavailable"} · Vector: {readiness.capabilities.vector ? "available" : "unavailable"} · Graph: {readiness.capabilities.graph ? "available" : "unavailable"}</p>
          <p className="mt-2 text-xs text-muted-foreground">{Object.entries(readiness.counts).map(([key, count]) => `${key}: ${count}`).join(" · ")}</p>
          <p className="mt-2 text-xs text-muted-foreground">Verified {new Date(readiness.verified_at).toLocaleString()}. Availability is rechecked by the backend on every query.</p>
          {readiness.failures.map((failure, index) => <p key={`${failure.stage}-${failure.code}-${index}`} className="mt-2 text-sm text-muted-foreground">{failure.stage}: {failure.code}{failure.retryable ? " (retry eligible)" : ""}</p>)}
        </> : null}
      </section>

      <form action={formAction} onSubmit={() => setSubmittedQuestion(message.trim())} aria-busy={pending} className="rounded-xl border bg-card p-5">
        <input type="hidden" name="project_id" value={project.id} />
        <input type="hidden" name="mode" value={mode} />
        <label htmlFor="question" className="block font-medium">Question</label>
        <textarea id="question" name="message" value={message} onChange={(event) => setMessage(event.target.value)} required readOnly={pending} aria-describedby="question-limit" placeholder="Ask about this corpus…" className="mt-3 min-h-32 w-full resize-y rounded-lg border bg-background p-3 text-sm focus-visible:ring-2 focus-visible:ring-ring" />
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
          <p id="question-limit" className={`text-xs ${questionBytes > 1024 ? "text-destructive" : "text-muted-foreground"}`}>{questionBytes} / 1,024 UTF-8 bytes. Each query is independent; chat memory is not enabled.</p>
          <Button type="submit" disabled={pending || checking || !modeAvailable(readiness, mode) || !questionBytes || questionBytes > 1024}>{pending ? "Retrieving and generating…" : "Ask corpus"}</Button>
        </div>
        <p role="status" className="mt-3 text-sm text-muted-foreground">{pending ? "Query running. Your question is preserved; source verification and generation may take several minutes." : !checking && !modeAvailable(readiness, mode) ? "Selected mode is unavailable. Refresh readiness or choose an available mode." : ""}</p>
      </form>

      {state.error ? <p role="alert" className="rounded-xl border border-destructive/30 bg-destructive/10 p-4 text-sm">{state.error}{state.code ? ` (${state.code})` : ""} Refresh readiness before retrying an unavailable index.</p> : null}
      {result && !pending ? <section aria-label="Query result" className="min-w-0 space-y-5">
        <div className="rounded-xl border p-5" role="status">
          <h2 className="font-semibold">{result.status === "answered" ? "Answer" : "Insufficient evidence"}</h2>
          <p className="mt-3 whitespace-pre-wrap break-words text-sm text-muted-foreground">Question: {submittedQuestion}</p>
          <p className="mt-2 text-xs text-muted-foreground">Mode: {result.mode} · Run: {result.query_run_id}</p>
          <div className="mt-4 whitespace-pre-wrap break-words text-sm leading-relaxed">
            {result.answer.split(/(\[S\d+\])/g).map((part, index) => {
              const cited = result.sources.find((item) => `[${item.label}]` === part);
              return cited ? <a key={index} href={passageHref(result.project_id, cited.chunk_id)} target="_blank" rel="noopener noreferrer" aria-label={`Open citation ${cited.label}`} className="font-medium text-primary underline underline-offset-4">{part}</a> : part;
            })}
          </div>
        </div>
        <div>
          <h2 className="mb-3 font-semibold">Cited sources ({result.sources.length})</h2>
          {result.sources.length ? <ul className="grid gap-3">{result.sources.map((source) => <SourceCard key={source.citation_id} source={source} projectId={result.project_id} />)}</ul> : <p className="text-sm text-muted-foreground">No sources cited. Retrieved candidates do not establish an answer.</p>}
        </div>
        <details className="rounded-xl border p-4"><summary className="cursor-pointer font-medium">Measured diagnostics and retrieved candidates</summary>
          <p className="mt-3 text-sm">Generation: {result.generation.called ? `${result.generation.provider} / ${result.generation.model}` : "not called"} · Fallback: {result.generation.fallback ? "yes" : "no"}</p>
          <pre className="mt-3 overflow-auto whitespace-pre-wrap break-all text-xs">{JSON.stringify({ ...result.retrieval_diagnostics, generation: result.generation, vector_generation: result.vector_generation, graph_generation: result.graph_generation }, null, 2)}</pre>
          <h3 className="my-3 text-sm font-medium">Context candidates — not necessarily cited</h3>
          <ul className="grid gap-3">{result.citation_candidates.map((source) => <SourceCard key={source.citation_id} source={source} projectId={result.project_id} />)}</ul>
        </details>
      </section> : !pending && !state.error ? <p className="text-sm text-muted-foreground">Ask a question to see an actual answer and source evidence.</p> : null}
    </div>
  );
}

export function PlaygroundClient({ projects, queryProjectAction, error }: Props) {
  const [projectId, setProjectId] = useState(projects[0]?.id || "");
  const project = projects.find((item) => item.id === projectId);
  return (
    <div className="min-h-[calc(100svh-4rem)] bg-background">
      <header className="border-b px-4 py-5 md:px-6"><h1 className="text-2xl font-semibold tracking-tight">Playground</h1><p className="mt-1 text-sm text-muted-foreground">Answers grounded in your selected corpus.</p></header>
      {error ? <p role="alert" className="p-6 text-sm">{error} Reload to retry.</p> : project ? <CorpusPlayground key={project.id} projects={projects} project={project} queryProjectAction={queryProjectAction} onProjectChange={setProjectId} /> : <div className="p-6"><p>No corpus available.</p><Link href="/dashboard/document" className="mt-3 inline-block text-primary underline">Create a corpus</Link></div>}
    </div>
  );
}
