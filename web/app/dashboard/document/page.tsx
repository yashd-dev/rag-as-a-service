import { AppDashboardShell } from "@/components/app-dashboard-shell";
import { listDataSources, listDocuments, listProjects } from "@/lib/backend";
import { createProjectAction, deleteDocumentAction, deleteProjectAction } from "@/lib/backend-actions";
import { getDashboardContext } from "@/lib/dashboard-context";
import { unstable_rethrow } from "next/navigation";
import { DocumentClient } from "./document-client";

export default async function DocumentPage() {
  const { session, organization, role } = await getDashboardContext();
  const projects = await listProjects();
  const dataSources = await listDataSources();
  const documentEntries = await Promise.all(
    projects.items.map(async (project) => [project.id, await listDocuments(project.id).then((response) => response.items).catch((error: unknown) => { unstable_rethrow(error); return null; })] as const)
  );
  const documentsByProject = Object.fromEntries(documentEntries);

  return (
    <AppDashboardShell active="documents" organizationName={organization.name} user={session.user} role={role}>
      <DocumentClient
        key={projects.items.map((project) => project.id).join(",")}
        projects={projects.items}
        dataSources={dataSources.items}
        documentsByProject={documentsByProject}
        createProjectAction={createProjectAction}
        deleteProjectAction={deleteProjectAction}
        deleteDocumentAction={deleteDocumentAction}
      />
    </AppDashboardShell>
  );
}
