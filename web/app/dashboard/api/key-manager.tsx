"use client";

import { useActionState, useState } from "react";
import type { KeyState, PlatformKey, Project } from "@/lib/backend";

type RevokeAction = (state: { error?: string }, data: FormData) => Promise<{ error?: string }>;

function KeyRow({ item, action }: { item: PlatformKey; action: RevokeAction }) {
  const [state, submit, pending] = useActionState(action, {});
  return <li className="space-y-2 rounded-lg border p-4 text-sm">
    <p className="font-medium">{item.name} · {item.prefix}… · {item.revoked_at ? "Revoked" : "Active"}</p>
    <p className="break-all text-muted-foreground">Corpora: {item.corpus_ids.join(", ") || "None remaining"} · {item.request_count} API requests</p>
    {item.revoked_at ? null : <form action={submit}><input type="hidden" name="key_id" value={item.id} /><button disabled={pending} type="submit" className="text-destructive underline">{pending ? "Revoking…" : "Revoke key"}</button></form>}
    {state.error ? <p role="alert">{state.error}</p> : null}
  </li>;
}

export function KeyManager({ keys, projects, createAction, revokeAction }: {
  keys: PlatformKey[]; projects: Project[];
  createAction: (state: KeyState, data: FormData) => Promise<KeyState>;
  revokeAction: RevokeAction;
}) {
  const [state, submit, pending] = useActionState(createAction, {});
  const [copyMessage, setCopyMessage] = useState("");
  return <div className="space-y-5">
    <form action={submit} className="space-y-4 rounded-xl border p-5">
      <label className="grid gap-2 text-sm font-medium">Key name<input name="name" required maxLength={80} placeholder="My server integration" className="h-11 rounded-lg border bg-background px-3" /></label>
      <fieldset className="space-y-2"><legend className="mb-2 text-sm font-medium">Allowed corpora (required)</legend>{projects.map((project) => <label key={project.id} className="flex items-center gap-3 text-sm"><input name="corpus_ids" type="checkbox" value={project.id} />{project.name} · {project.read_only ? "Shared legal (read-only)" : "Private"}</label>)}</fieldset>
      {!projects.length ? <p className="text-sm">Create a corpus before creating an API key.</p> : null}
      <button type="submit" disabled={pending || !projects.length} className="rounded-lg bg-primary px-4 py-3 text-sm text-primary-foreground disabled:opacity-50">{pending ? "Creating…" : "Create API key"}</button>
      {state.error ? <p role="alert" className="text-sm text-destructive">{state.error}</p> : null}
    </form>
    {state.created ? <section className="space-y-3 rounded-xl border p-5" aria-label="New API key">
      <h2 className="font-medium">Copy this key now — it is shown only on creation.</h2>
      <code className="block break-all rounded border p-3">{state.created.key}</code>
      <button type="button" className="text-sm text-primary underline" onClick={async () => { try { await navigator.clipboard.writeText(state.created!.key); setCopyMessage("Copied"); } catch { setCopyMessage("Copy unavailable; select and copy the key above."); } }}>Copy key</button>
      <p role="status" className="text-sm">{copyMessage}</p>
    </section> : null}
    <ul className="space-y-3">{keys.map((item) => <KeyRow key={item.id} item={item} action={revokeAction} />)}</ul>
  </div>;
}
