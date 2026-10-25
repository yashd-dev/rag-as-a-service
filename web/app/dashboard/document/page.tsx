import { AppDashboardShell } from "@/components/app-dashboard-shell";
import { listDataSources, listProjects } from "@/lib/backend";
import { createProjectAction, deleteDocumentAction, deleteProjectAction } from "@/lib/backend-actions";
import { getDashboardContext } from "@/lib/dashboard-context";
import { DocumentClient } from "./document-client";

export default async function DocumentPage() {
  const [{ session, organization, role }, projects, dataSources] = await Promise.all([
    getDashboardContext(),
    listProjects(),
    listDataSources(),
  ]);

  return (
    <AppDashboardShell active="documents" organizationName={organization.name} user={session.user} role={role}>
      <DocumentClient
        key={projects.items.map((project) => project.id).join(",")}
        projects={projects.items}
        dataSources={dataSources.items}
        createProjectAction={createProjectAction}
        deleteProjectAction={deleteProjectAction}
        deleteDocumentAction={deleteDocumentAction}
      />
    </AppDashboardShell>
  );
}
