"use client";

import { useState, useSyncExternalStore } from "react";
import Link from "next/link";
import { integrationExamples } from "@/lib/integration-code";
import type { RetrievalMode } from "@/lib/rag-contract";
import { MonacoCodeEditor } from "./monaco-code-editor";

const subscribe = () => () => {};

export function IntegrationPanel({ corpusId, model, message, mode, available, onHide }: {
  corpusId: string; model: string; message: string; mode: RetrievalMode; available: boolean; onHide: () => void;
}) {
  const baseUrl = useSyncExternalStore(subscribe, () => window.location.origin + "/v1", () => "");
  const [language, setLanguage] = useState<"python" | "javascript" | "curl">("python");
  const [stream, setStream] = useState(false);
  const [copyStatus, setCopyStatus] = useState("");
  const code = integrationExamples({ baseUrl, corpusId, model, message, mode, stream })[language];
  return <aside aria-label="Integration code" className="min-w-0 space-y-4 rounded-xl border bg-card p-4 lg:sticky lg:top-6 lg:self-start">
    <div className="flex items-center justify-between gap-3"><h2 className="font-medium">Integration code</h2><button type="button" onClick={onHide} className="text-sm text-primary underline">Hide code</button></div>
    <p className="text-xs text-muted-foreground">Matches your selected corpus, answer configuration, question and retrieval mode. Use a corpus-scoped API key from <Link className="text-primary underline" href="/dashboard/api">API keys</Link>. Run examples on your server.</p>
    <label className="grid gap-2 text-sm">Language<select value={language} onChange={(event) => setLanguage(event.target.value as typeof language)} className="h-10 rounded-lg border bg-background px-3"><option value="python">Python</option><option value="javascript">JavaScript</option><option value="curl">cURL</option></select></label>
    <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={stream} onChange={(event) => setStream(event.target.checked)} />Stream integration response</label>
    <p className="text-xs text-muted-foreground">Streaming emits validated answer chunks after grounding completes. This toggle changes the examples; the playground waits for the complete validated result.</p>
    {!available ? <p role="status" className="text-sm">Choose an available answer provider to generate integration examples.</p> : !baseUrl ? <p className="text-sm">Loading API base URL…</p> : <>
      <p className="break-all text-xs text-muted-foreground">API base: {baseUrl}</p>
      <div className="h-[480px] min-w-0 overflow-hidden rounded-lg border"><MonacoCodeEditor language={language === "curl" ? "shell" : language} value={code} readOnly /></div>
      <button type="button" className="text-sm text-primary underline" onClick={async () => { try { await navigator.clipboard.writeText(code); setCopyStatus("Copied code"); } catch { setCopyStatus("Copy unavailable; select the code manually."); } }}>Copy code</button>
      <p role="status" className="text-xs">{copyStatus}</p>
    </>}
  </aside>;
}
