import { AppDashboardShell } from "@/components/app-dashboard-shell";
import { listCredentials } from "@/lib/backend";
import { createCredentialAction } from "@/lib/backend-actions";
import { getDashboardContext } from "@/lib/dashboard-context";
import { LlmClient } from "./llm-client";

export default async function LlmPage() {
  const { session, organization, role } = await getDashboardContext();
  const credentials = await listCredentials();

  return (
    <AppDashboardShell active="llm" organizationName={organization.name} user={session.user} role={role}>
      <LlmClient credentials={credentials.items} createCredentialAction={createCredentialAction} />
    </AppDashboardShell>
  );
}
