import { AppDashboardShell } from "@/components/app-dashboard-shell";
import { listGenerationConfigs, listProjects } from "@/lib/backend";
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
  const configs = await listGenerationConfigs().catch((error: unknown) => { unstable_rethrow(error); return null; });

  return (
    <AppDashboardShell active="playground" organizationName={organization.name} user={session.user} role={role}>
      <PlaygroundClient projects={projects?.items || []} generationConfigs={configs?.items || []} queryProjectAction={queryProjectAction} error={projects && configs ? undefined : "Could not load corpora or answer providers from the backend."} />
    </AppDashboardShell>
  );
}
