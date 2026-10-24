import Link from "next/link";
import { unstable_rethrow } from "next/navigation";
import { AppDashboardShell } from "@/components/app-dashboard-shell";
import { BackendError, sourcePassage } from "@/lib/backend";
import { getDashboardContext } from "@/lib/dashboard-context";
import { safeSourceUri } from "@/lib/rag-contract";

export default async function PassagePage({ params }: { params: Promise<{ projectId: string; chunkId: string }> }) {
  const { projectId, chunkId } = await params;
  const { session, organization, role } = await getDashboardContext();
  const { passage, error } = await sourcePassage(projectId, chunkId).then((passage) => ({ passage, error: undefined })).catch((cause: unknown) => {
    unstable_rethrow(cause);
    return { passage: null, error: cause instanceof BackendError ? cause.message : "Source unavailable, timed out, or returned an invalid response. Reload to retry." };
  });
  const uri = safeSourceUri(passage?.source_uri || null);
  return (
    <AppDashboardShell active="playground" organizationName={organization.name} user={session.user} role={role}>
      <section aria-label="Source passage" className="mx-auto w-full max-w-4xl space-y-5 p-4 md:p-8">
        <Link href="/dashboard/playground" className="text-sm text-primary underline">Back to playground</Link>
        <h1 className="break-words text-2xl font-semibold">Source passage</h1>
        {passage ? <>
          <h2 className="break-words font-medium">{passage.file_name || passage.document_id}</h2>
          <p className="text-sm">{passage.is_current_generation ? "Current source generation" : "Historical source generation — retained evidence, not the current index"}</p>
          <p className="text-sm text-muted-foreground">Characters {passage.start_char}–{passage.end_char} · {passage.pages.length ? `Pages ${passage.pages.map((page) => page.page).join(", ")}` : "Page numbers unavailable in this source"}</p>
          <blockquote className="whitespace-pre-wrap break-words rounded-xl border bg-card p-5 text-sm leading-relaxed">{passage.content}</blockquote>
          <dl className="space-y-2 break-all text-xs text-muted-foreground"><dt>Document</dt><dd>{passage.document_id}</dd><dt>Chunk</dt><dd>{passage.chunk_id}</dd><dt>Generation</dt><dd>{passage.generation_id}</dd><dt>Verified content hash</dt><dd>{passage.content_hash}</dd></dl>
          {uri ? <a href={uri} target="_blank" rel="noopener noreferrer" className="inline-block text-sm text-primary underline">Open original source</a> : null}
        </> : <p role="alert" className="rounded-xl border p-4 text-sm">{error}</p>}
      </section>
    </AppDashboardShell>
  );
}
