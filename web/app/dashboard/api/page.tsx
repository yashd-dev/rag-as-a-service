import { AppDashboardShell } from "@/components/app-dashboard-shell";
import Link from "next/link";
import { listPlatformKeys, listProjects } from "@/lib/backend";
import { createPlatformKeyAction, revokePlatformKeyAction } from "@/lib/backend-actions";
import { getDashboardContext } from "@/lib/dashboard-context";
import { KeyManager } from "./key-manager";

export default async function ApiPage() {
  const { session, organization, role } = await getDashboardContext();
  const [keys, projects] = await Promise.all([listPlatformKeys(), listProjects()]);
  return <AppDashboardShell active="api" organizationName={organization.name} user={session.user} role={role}>
    <div className="mx-auto w-full max-w-5xl space-y-6 p-4 md:p-8">
      <h1 className="text-2xl font-semibold">API keys and integration</h1>
      <p className="text-sm text-muted-foreground">Create a revocable server-side key restricted to explicitly selected corpora. Provider credentials remain separate and encrypted.</p>
      <KeyManager keys={keys.items} projects={projects.items} createAction={createPlatformKeyAction} revokeAction={revokePlatformKeyAction} />
      <section id="usage" className="space-y-3 rounded-xl border p-5"><h2 className="font-medium">OpenAI-compatible RAG API</h2>
        <p className="text-sm">POST /v1/chat/completions · GET /v1/models · GET /v1/corpora/:corpus_id/passages/:chunk_id</p>
        <p className="text-sm text-muted-foreground">Send one user message, an explicit corpus_id and a model configuration ID from the playground. Streaming sends validated answer chunks and final citations, not unverified live provider tokens. Each request is independent.</p>
        <p className="text-sm text-muted-foreground">Limits: 1,024 UTF-8 question bytes; 16 KiB JSON; 20 requests/minute per key and 60 requests/minute per workspace. Temperature is fixed at 0 and output limit at 1,024 tokens. Other generation values, tools and conversation history are rejected.</p>
        <Link href="/dashboard/playground" className="inline-block text-sm text-primary underline">Open playground for Python, JavaScript and cURL examples</Link>
      </section>
    </div>
  </AppDashboardShell>;
}
