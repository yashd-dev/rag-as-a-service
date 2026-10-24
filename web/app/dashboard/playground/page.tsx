import { AppDashboardShell } from "@/components/app-dashboard-shell";
import { listProjects } from "@/lib/backend";
import { queryProjectAction } from "@/lib/backend-actions";
import { getDashboardContext } from "@/lib/dashboard-context";
import { unstable_rethrow } from "next/navigation";
import { PlaygroundClient } from "./playground-client";

export default async function PlaygroundPage() {
  const { session, organization, role } = await getDashboardContext();
  const projects = await listProjects().catch((error: unknown) => {
    unstable_rethrow(error);
    return null;
  });

  return (
    <AppDashboardShell active="playground" organizationName={organization.name} user={session.user} role={role}>
      <PlaygroundClient projects={projects?.items || []} queryProjectAction={queryProjectAction} error={projects ? undefined : "Could not load corpora from the backend."} />
    </AppDashboardShell>
  );
}
