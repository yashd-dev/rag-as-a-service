"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { IngestionJob } from "@/lib/backend";

export function JobProgress({ projectId }: { projectId: string }) {
  const [jobs, setJobs] = useState<IngestionJob[]>([]);
  const [error, setError] = useState("");
  const previous = useRef("");
  const router = useRouter();
  useEffect(() => {
    const controller = new AbortController();
    let busy = false;
    async function load() {
      if (busy) return;
      busy = true;
      try {
        const response = await fetch(`/api/projects/${encodeURIComponent(projectId)}/jobs`, { cache: "no-store", signal: AbortSignal.any([controller.signal, AbortSignal.timeout(15_000)]) });
        if (!response.ok) throw new Error("Ingestion status unavailable. Retry when the backend is reachable.");
        const data = await response.json();
        if (!Array.isArray(data.items)) throw new Error("Invalid ingestion status");
        if (controller.signal.aborted) return;
        const signature = JSON.stringify(data.items.map((job: IngestionJob) => [job.document_id, job.state]));
        if (previous.current && previous.current !== signature && data.items.some((job: IngestionJob) => job.state === "completed")) router.refresh();
        previous.current = signature;
        setJobs(data.items); setError("");
      } catch (cause) {
        if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "Ingestion status unavailable");
      } finally { busy = false; }
    }
    void load();
    const interval = setInterval(() => { void load(); }, 3000);
    return () => { controller.abort(); clearInterval(interval); };
  }, [projectId, router]);

  async function retry(documentId: string) {
    try {
      const response = await fetch(`/api/projects/${encodeURIComponent(projectId)}/jobs/${encodeURIComponent(documentId)}/retry`, { method: "POST" });
      if (!response.ok) throw new Error("Could not retry this job. It may already be running.");
      setError("");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Retry unavailable"); }
  }

  return <section aria-label="Automatic indexing" className="space-y-3 rounded-xl border p-4">
    <div className="flex items-center justify-between gap-3"><h2 className="font-medium">Automatic indexing</h2><button type="button" className="text-sm text-primary underline" onClick={() => router.refresh()}>Refresh readiness</button></div>
    <p className="text-sm text-muted-foreground">Uploads are processed by the background worker. Text, vector and graph readiness are verified separately.</p>
    {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
    <ul className="space-y-2" aria-live="polite">{jobs.map((job) => <li key={job.document_id} className="break-all rounded-lg border p-3 text-sm">
      <p>{job.document_id} · {job.state} · {job.stage}</p><p className="text-muted-foreground">Attempt {job.attempts} · {job.vector_count}/{job.chunk_count} vectors</p>
      {job.error_code ? <p className="text-destructive">{job.error_code.replaceAll("_", " ")}{job.state === "queued" ? " — automatic retry pending" : ""}</p> : null}
      {job.state === "failed" ? <button type="button" onClick={() => { void retry(job.document_id); }} className="mt-2 text-primary underline">Retry indexing</button> : null}
    </li>)}</ul>
  </section>;
}
