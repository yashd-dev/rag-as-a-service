"use client";

import { useState } from "react";
import { ArrowLeft, ChevronDown, Copy, HelpCircle, Plus, RefreshCw, Search, X, Zap } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { Credential } from "@/lib/backend";

const llms = [
  { id: "llm_3875912", name: "mockingbird-2024-06-18-experimental", description: "Recall's experimental summarization model for RAG answers." },
  { id: "llm_4875912", name: "mockingbird-1.0", description: "Mockingbird LLM v1.0 prompt for summarizing query results as an answer." },
  { id: "llm_5875912", name: "mockingbird-2.0", description: "Mockingbird LLM v2.0 prompt for summarizing query results as an answer." },
  { id: "llm_6875912", name: "qwen2.5-7b-instruct", description: "Qwen/Qwen2.5-7B-Instruct base model for answer generation." },
  { id: "llm_7747127", name: "gpt-3.5-turbo", description: "OpenAI's GPT-3.5 Turbo model." },
  { id: "llm_9236343", name: "gpt-4", description: "OpenAI's GPT-4 model." },
  { id: "llm_53462110", name: "gpt-4o", description: "OpenAI's GPT-4o model." },
  { id: "llm_53462112", name: "gpt-4o-mini", description: "OpenAI's GPT-4o-mini model." },
  { id: "llm_520721868", name: "gpt-5", description: "OpenAI GPT-5 model." },
  { id: "llm_520721869", name: "gpt-5-mini", description: "OpenAI GPT-5 Mini model." },
  { id: "llm_520721870", name: "gpt-5-nano", description: "OpenAI GPT-5 Nano model." },
  { id: "llm_520721923", name: "gpt-5.2", description: "OpenAI GPT-5.2 model." },
  { id: "llm_520722003", name: "gpt-5.4", description: "OpenAI GPT-5.4 model." },
  { id: "llm_520722203", name: "gpt-5.5", description: "OpenAI GPT-5.5 model." },
  { id: "llm_520722277", name: "GPT 5.6 Terra", description: "OpenAI GPT-5.6 Terra, balanced tier." },
  { id: "llm_520722278", name: "Luna", description: "OpenAI GPT-5.6 Luna, fast cost-efficient tier." },
];

type Llm = (typeof llms)[number];
type LlmClientProps = {
  credentials: Credential[];
  createCredentialAction: (formData: FormData) => void;
};

function llmJson(llm: Llm) {
  return `{
  "id": "${llm.id}",
  "name": "${llm.name}",
  "description": "${llm.description}",
  "enabled": true,
  "capabilities": {
    "image_support": true,
    "context_limit": 128000,
    "tool_calling": true,
    "structured_outputs": true
  },
  "ownership": "platform",
  "type": "openai-compatible",
  "model": "${llm.name}",
  "uri": "https://api.openai.com/v1/chat/completions",
  "headers": {},
  "auth": {
    "type": "bearer",
    "token": "****"
  }
}`;
}

function Badge({ children }: { children: React.ReactNode }) {
  return <span className="rounded-full bg-secondary px-2.5 py-1 text-xs text-muted-foreground">{children}</span>;
}

export function LlmClient({ credentials, createCredentialAction }: LlmClientProps) {
  const [view, setView] = useState<"list" | "add">("list");
  const [selected, setSelected] = useState<Llm | null>(null);

  if (view === "add") {
    return (
      <div className="mx-auto flex w-full max-w-4xl flex-col gap-8 p-4 md:p-8">
        <button onClick={() => setView("list")} className="flex w-fit items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-4" />
          Back
        </button>

        <div className="flex flex-col gap-3">
          <h1 className="text-3xl font-semibold tracking-tight">Add LLM</h1>
          <p className="text-sm text-muted-foreground">
            Paste a provider key. We&apos;ll list the models it can reach and check that one of them responds. <span className="text-primary">Learn more</span>
          </p>
        </div>

        <form action={createCredentialAction} className="flex flex-col gap-6">
          <label className="flex flex-col gap-2">
            <span className="text-sm font-medium tracking-tight">Name</span>
            <input name="name" defaultValue="OpenAI" className="h-11 rounded-lg border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring" />
          </label>
          <div className="grid gap-4 md:grid-cols-2">
            <label className="flex flex-col gap-2">
              <span className="text-sm font-medium tracking-tight">Provider</span>
              <select name="provider" defaultValue="openai" className="h-11 rounded-lg border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"><option value="openai">OpenAI</option><option value="ollama">Ollama</option><option value="unstructured">Unstructured</option></select>
            </label>
            <label className="flex flex-col gap-2">
              <span className="text-sm font-medium tracking-tight">Credential type</span>
              <select name="credential_type" defaultValue="llm" className="h-11 rounded-lg border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"><option value="llm">LLM</option><option value="embedding">Embedding</option><option value="ocr">OCR</option></select>
            </label>
          </div>
          <label className="flex flex-col gap-2">
            <span className="text-sm font-medium tracking-tight">API key or credentials</span>
            <span className="text-sm text-muted-foreground">Paste an API key, or a full credential such as a Google service-account JSON. We detect the provider automatically.</span>
            <textarea name="api_key" autoFocus placeholder="sk-..." className="min-h-28 rounded-lg border bg-background p-3 text-sm outline-none focus:ring-2 focus:ring-ring" />
          </label>

          <label className="flex flex-col gap-2">
            <span className="text-sm font-medium tracking-tight">Endpoint URL (required)</span>
            <span className="text-sm text-muted-foreground">The endpoint to probe. A URL alone works for unauthenticated or self-hosted OpenAI-compatible servers.</span>
            <input name="base_url" placeholder="https://my-endpoint.example/v1/chat/completions" className="h-11 rounded-lg border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring" />
          </label>

          <label className="flex flex-col gap-2">
            <span className="text-sm font-medium tracking-tight">Default model</span>
            <input name="default_model" defaultValue="gpt-4o-mini" className="h-11 rounded-lg border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring" />
          </label>

          <div className="flex items-center justify-between">
            <button type="button" className="text-sm font-medium text-primary">Enter details manually</button>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setView("list")} className="h-11 px-5 font-normal">Cancel</Button>
              <Button className="h-11 gap-2 px-5 font-normal"><Search className="size-4" />Save credential</Button>
            </div>
          </div>
        </form>
      </div>
    );
  }

  return (
    <div className="relative min-h-[calc(100svh-4rem)] overflow-hidden bg-background">
      <div className="flex h-16 items-center justify-between border-b px-4 md:px-6">
        <div className="flex items-center gap-3">
          <h1 className="font-medium tracking-tight">LLMs</h1>
          <span className="text-muted-foreground">/</span>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <input placeholder="Search LLMs" className="h-9 w-64 rounded-lg border bg-background pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-ring" />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" className="h-9 gap-2 px-3 font-normal"><HelpCircle className="size-4" />Help</Button>
          <Button variant="outline" className="h-9 gap-2 px-3 font-normal"><RefreshCw className="size-4" />Reload</Button>
          <Button onClick={() => setView("add")} className="h-9 gap-2 px-3 font-normal"><Plus className="size-4" />Add LLM</Button>
        </div>
      </div>

      <div className="p-4 md:p-6">
        <div className="overflow-hidden rounded-xl border bg-background">
          <div className="grid grid-cols-[28px_130px_360px_1fr_100px_44px] gap-3 border-b bg-secondary px-3 py-3 text-sm font-medium">
            <span><input type="checkbox" className="size-4 rounded border" /></span>
            <span>ID</span>
            <span>Name</span>
            <span>Description</span>
            <span>Enabled</span>
            <span />
          </div>
          {credentials.map((credential) => (
            <div key={credential.id} className="grid grid-cols-[28px_130px_360px_1fr_100px_44px] items-center gap-3 border-b px-3 py-2.5 text-sm hover:bg-card">
              <input type="checkbox" className="size-4 rounded border" />
              <button className="truncate text-left font-medium text-primary">{credential.id}</button>
              <div className="flex min-w-0 items-center gap-2">
                <span className="truncate">{credential.name}</span>
                <Badge>BYOK</Badge>
              </div>
              <p className="truncate text-muted-foreground">{credential.provider} {credential.default_model || credential.default_embedding_model || credential.credential_type}</p>
              <span className="w-fit rounded-full bg-green-100 px-2.5 py-1 text-xs text-green-700">{credential.status}</span>
              <Button variant="outline" size="icon-sm"><ChevronDown className="size-3.5" /></Button>
            </div>
          ))}
          {llms.map((llm) => (
            <div key={llm.id} className="grid grid-cols-[28px_130px_360px_1fr_100px_44px] items-center gap-3 border-b px-3 py-2.5 text-sm last:border-b-0 hover:bg-card">
              <input type="checkbox" className="size-4 rounded border" />
              <button onClick={() => setSelected(llm)} className="truncate text-left font-medium text-primary">{llm.id}</button>
              <div className="flex min-w-0 items-center gap-2">
                <span className="truncate">{llm.name}</span>
                <Badge>Platform</Badge>
              </div>
              <p className="truncate text-muted-foreground">{llm.description}</p>
              <span className="w-fit rounded-full bg-green-100 px-2.5 py-1 text-xs text-green-700">Enabled</span>
              <Button variant="outline" size="icon-sm" onClick={() => setSelected(llm)}><ChevronDown className="size-3.5" /></Button>
            </div>
          ))}
        </div>
        <div className="mt-4 flex gap-4 text-sm text-muted-foreground">
          <button>← Previous</button>
          <button>Next →</button>
        </div>
      </div>

      {selected ? (
        <div className="absolute inset-0 z-40 flex bg-foreground/45">
          <button aria-label="Close LLM details" className="flex-1" onClick={() => setSelected(null)} />
          <aside className="flex w-full max-w-2xl flex-col overflow-y-auto bg-background shadow-xl">
            <div className="flex h-16 items-center justify-between border-b px-6">
              <div className="flex items-center gap-2 font-semibold tracking-tight"><Zap className="size-4 text-primary" />LLM details</div>
              <button onClick={() => setSelected(null)}><X className="size-4" /></button>
            </div>
            <div className="flex flex-col gap-6 p-6">
              <div>
                <p className="text-sm font-medium tracking-tight">ID</p>
                <p className="mt-2 text-sm text-muted-foreground">{selected.id}</p>
              </div>
              <div>
                <p className="text-sm font-medium tracking-tight">Name</p>
                <p className="mt-2 text-sm">{selected.name}</p>
              </div>
              <div>
                <p className="text-sm font-medium tracking-tight">Description</p>
                <p className="mt-2 text-sm">{selected.description}</p>
              </div>
              <div>
                <p className="text-sm font-medium tracking-tight">Ownership</p>
                <div className="mt-2"><Badge>Platform</Badge></div>
              </div>
              <div>
                <div className="mb-3 flex items-center justify-between">
                  <p className="text-sm font-medium tracking-tight">JSON</p>
                  <Button variant="ghost" size="icon-sm"><Copy className="size-3.5" /></Button>
                </div>
                <pre className="overflow-auto rounded-xl bg-secondary p-5 text-xs leading-6 text-foreground"><code>{llmJson(selected)}</code></pre>
              </div>
            </div>
          </aside>
        </div>
      ) : null}
    </div>
  );
}
