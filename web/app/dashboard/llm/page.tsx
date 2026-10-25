import { AppDashboardShell } from "@/components/app-dashboard-shell";
import { listCredentials, listGenerationConfigs } from "@/lib/backend";
import { createCredentialAction, credentialControlAction } from "@/lib/backend-actions";
import { getDashboardContext } from "@/lib/dashboard-context";
import { LlmClient } from "./llm-client";

export default async function LlmPage() {
  const { session, organization, role } = await getDashboardContext();
  const credentials = await listCredentials();
  const configs = await listGenerationConfigs();

  return (
    <AppDashboardShell active="llm" organizationName={organization.name} user={session.user} role={role}>
      <LlmClient key={credentials.items.map((item) => item.id).join(",")} generationConfigs={configs.items} userId={session.user.id} credentials={credentials.items} createCredentialAction={createCredentialAction} controlAction={credentialControlAction} />
    </AppDashboardShell>
  );
}
