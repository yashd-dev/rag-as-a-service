import { AppDashboardShell } from "@/components/app-dashboard-shell";
import { listDocuments, listProjects } from "@/lib/backend";
import { createProjectAction, deleteDocumentAction, deleteProjectAction } from "@/lib/backend-actions";
import { getDashboardContext } from "@/lib/dashboard-context";
import { DocumentClient } from "./document-client";

export default async function DocumentPage() {
  const { session, organization, role } = await getDashboardContext();
  const projects = await listProjects();
  const documentEntries = await Promise.all(
    projects.items.map(async (project) => [project.id, (await listDocuments(project.id)).items] as const)
  );
  const documentsByProject = Object.fromEntries(documentEntries);

  return (
    <AppDashboardShell active="documents" organizationName={organization.name} user={session.user} role={role}>
      <DocumentClient
        projects={projects.items}
        documentsByProject={documentsByProject}
        createProjectAction={createProjectAction}
        deleteProjectAction={deleteProjectAction}
        deleteDocumentAction={deleteDocumentAction}
      />
    </AppDashboardShell>
  );
}
