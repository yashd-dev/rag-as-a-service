import { AppDashboardShell } from "@/components/app-dashboard-shell";
import { listProjects } from "@/lib/backend";
import { createProjectAction, deleteProjectAction } from "@/lib/backend-actions";
import { getDashboardContext } from "@/lib/dashboard-context";
import { DocumentClient } from "./document-client";

export default async function DocumentPage() {
  const { session, organization, role } = await getDashboardContext();
  const projects = await listProjects();

  return (
    <AppDashboardShell active="documents" organizationName={organization.name} user={session.user} role={role}>
      <DocumentClient projects={projects.items} createProjectAction={createProjectAction} deleteProjectAction={deleteProjectAction} />
    </AppDashboardShell>
  );
}
