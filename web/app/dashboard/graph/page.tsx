import { AppDashboardShell } from "@/components/app-dashboard-shell";
import { Button } from "@/components/ui/button";
import { graphHtmlUrl, graphStatus, listProjects } from "@/lib/backend";
import { getDashboardContext } from "@/lib/dashboard-context";

export default async function GraphPage() {
  const { session, organization, role } = await getDashboardContext();
  const projects = await listProjects();
  const project = projects.items[0];
  const status = project ? await graphStatus(project.id) : null;

  return (
    <AppDashboardShell active="graph" organizationName={organization.name} user={session.user} role={role}>
      <div className="flex min-h-[calc(100svh-4rem)] flex-col bg-background">
        <div className="flex h-16 items-center justify-between border-b px-4 md:px-6">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Graph</h1>
            <p className="text-sm text-muted-foreground">Neo4j-backed entity graph for the active corpus.</p>
          </div>
          <Button variant="outline" className="h-9 px-3 font-normal">Refresh</Button>
        </div>

        {!project ? (
          <div className="grid flex-1 place-items-center p-6 text-center">
            <div className="max-w-lg">
              <h2 className="text-2xl font-semibold tracking-tight">Create a corpus first</h2>
              <p className="mt-3 text-sm text-muted-foreground">The graph appears after documents are indexed into Neo4j.</p>
            </div>
          </div>
        ) : (
          <div className="grid flex-1 gap-4 p-4 md:grid-cols-[260px_1fr] md:p-6">
            <aside className="rounded-xl border bg-card p-4">
              <p className="text-xs uppercase tracking-wide text-muted-foreground">Corpus</p>
              <h2 className="mt-2 font-medium tracking-tight">{project.name}</h2>
              <div className="mt-6 grid gap-3 text-sm">
                <div className="rounded-lg bg-background p-3">
                  <p className="text-muted-foreground">Nodes</p>
                  <p className="mt-1 text-2xl font-semibold">{status?.node_count || 0}</p>
                </div>
                <div className="rounded-lg bg-background p-3">
                  <p className="text-muted-foreground">Edges</p>
                  <p className="mt-1 text-2xl font-semibold">{status?.edge_count || 0}</p>
                </div>
              </div>
            </aside>
            <div className="overflow-hidden rounded-xl border bg-card">
              <iframe title="Knowledge graph" src={graphHtmlUrl(project.id)} className="h-full min-h-[640px] w-full" />
            </div>
          </div>
        )}
      </div>
    </AppDashboardShell>
  );
}
