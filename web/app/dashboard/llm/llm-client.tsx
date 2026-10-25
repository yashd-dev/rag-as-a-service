"use client";

import { useActionState, useState } from "react";
import { ArrowLeft, ChevronDown, HelpCircle, Plus, RefreshCw, Search, X, Zap } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { Credential, GenerationConfig } from "@/lib/backend";

type Llm = GenerationConfig & { description: string };
type LlmClientProps = {
  credentials: Credential[];
  generationConfigs: GenerationConfig[];
  userId: string;
  controlAction: (state: { error?: string }, data: FormData) => Promise<{ error?: string }>;
  createCredentialAction: (state: { error?: string } | undefined, formData: FormData) => Promise<{ error?: string } | undefined>;
};

function CredentialControls({ credential, action }: { credential: Credential; action: LlmClientProps["controlAction"] }) {
  const [state, submit, pending] = useActionState(action, {});
  return <form action={submit} className="flex flex-wrap gap-2 text-xs">
    <input type="hidden" name="credential_id" value={credential.id} />
    <button type="submit" name="operation" value="validate" disabled={pending || credential.status === "revoked"} className="text-primary underline">Validate</button>
    <button type="submit" name="operation" value="revoke" disabled={pending || credential.status === "revoked"} className="text-destructive underline">Revoke</button>
    {state.error ? <span role="alert">{state.error}</span> : null}
  </form>;
}

function llmJson(llm: Llm) {
  return JSON.stringify({ id: llm.id, name: llm.name, model: llm.model, available: llm.available, ownership: "platform" }, null, 2);
}

function Badge({ children }: { children: React.ReactNode }) {
  return <span className="rounded-full bg-secondary px-2.5 py-1 text-xs text-muted-foreground">{children}</span>;
}

export function LlmClient({ credentials, generationConfigs, createCredentialAction, controlAction, userId }: LlmClientProps) {
  const [saveState, saveAction, saving] = useActionState(createCredentialAction, undefined);
  const [view, setView] = useState<"list" | "add">("list");
  const [selected, setSelected] = useState<Llm | null>(null);
  const llms = generationConfigs.filter((item) => item.id.startsWith("platform:")).map((item) => ({ ...item, description: item.available ? `Configured answer model: ${item.model}` : "Platform key/model must be configured before use." }));

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
            Add a supported HTTPS provider endpoint, model and key. Saved credentials are validated and can be selected in the playground and API.
          </p>
        </div>

        <form action={saveAction} className="flex flex-col gap-6">
          {saveState?.error ? <p role="alert" className="text-sm text-destructive">{saveState.error}</p> : null}
          <label className="flex flex-col gap-2">
            <span className="text-sm font-medium tracking-tight">Name</span>
            <input name="name" defaultValue="OpenAI" className="h-11 rounded-lg border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring" />
          </label>
          <div className="grid gap-4 md:grid-cols-2">
            <label className="flex flex-col gap-2">
              <span className="text-sm font-medium tracking-tight">Provider</span>
              <select name="provider" defaultValue="openai-compatible" className="h-11 rounded-lg border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"><option value="openai-compatible">OpenAI-compatible</option><option value="openai">OpenAI</option><option value="gemini">Gemini OpenAI-compatible</option><option value="ollama">Ollama</option></select>
            </label>
            <label className="flex flex-col gap-2">
              <span className="text-sm font-medium tracking-tight">Credential type</span>
              <select name="credential_type" defaultValue="llm" className="h-11 rounded-lg border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring"><option value="llm">LLM</option><option value="embedding">Embedding</option><option value="ocr">OCR</option></select>
            </label>
          </div>
          <label className="flex flex-col gap-2">
            <span className="text-sm font-medium tracking-tight">API key or credentials</span>
            <span className="text-sm text-muted-foreground">Provider API key only. Stored encrypted and never included in integration code.</span>
            <textarea name="api_key" autoFocus placeholder="sk-..." className="min-h-28 rounded-lg border bg-background p-3 text-sm outline-none focus:ring-2 focus:ring-ring" />
          </label>

          <label className="flex flex-col gap-2">
            <span className="text-sm font-medium tracking-tight">Endpoint URL (required)</span>
            <span className="text-sm text-muted-foreground">Use the base URL, not the full chat completions path.</span>
            <input name="base_url" placeholder="https://my-endpoint.example/v1" className="h-11 rounded-lg border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring" />
          </label>

          <label className="flex flex-col gap-2">
            <span className="text-sm font-medium tracking-tight">Default model</span>
            <input name="default_model" defaultValue="gpt-4o-mini" className="h-11 rounded-lg border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring" />
          </label>
          <label className="flex items-center gap-3 text-sm"><input type="checkbox" name="is_org_shared" />Share this credential with this workspace (otherwise only you can use it)</label>

          <div className="flex items-center justify-between">
            <button type="button" className="text-sm font-medium text-primary">Enter details manually</button>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => setView("list")} className="h-11 px-5 font-normal">Cancel</Button>
              <Button type="submit" disabled={saving} className="h-11 gap-2 px-5 font-normal"><Search className="size-4" />{saving ? "Validating…" : "Save credential"}</Button>
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
              {credential.owner_user_id === userId ? <CredentialControls credential={credential} action={controlAction} /> : <span className="text-xs text-muted-foreground">Shared</span>}
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
              <span className="w-fit rounded-full bg-secondary px-2.5 py-1 text-xs">{llm.available ? "Configured" : "Unavailable"}</span>
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
