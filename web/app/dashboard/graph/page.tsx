import { AppDashboardShell } from "@/components/app-dashboard-shell";
import { graphStatus, listProjects } from "@/lib/backend";
import { getDashboardContext } from "@/lib/dashboard-context";
import { GraphClient } from "./graph-client";

export default async function GraphPage() {
  const { session, organization, role } = await getDashboardContext();
  const projects = await listProjects();
  const project = projects.items[0];
  const status = project ? await graphStatus(project.id) : null;

  return (
    <AppDashboardShell active="graph" organizationName={organization.name} user={session.user} role={role}>
      {!project ? (
        <div className="flex min-h-[calc(100svh-4rem)] flex-col bg-background">
          <div className="grid flex-1 place-items-center p-6 text-center">
            <div className="max-w-lg">
              <h2 className="text-2xl font-semibold tracking-tight">Create a corpus first</h2>
              <p className="mt-3 text-sm text-muted-foreground">The graph appears after documents are indexed into Neo4j.</p>
            </div>
          </div>
        </div>
      ) : (
        <GraphClient project={project} initialStatus={status} />
      )}
    </AppDashboardShell>
  );
}
