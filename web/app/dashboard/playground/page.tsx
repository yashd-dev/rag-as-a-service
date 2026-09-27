import { headers } from "next/headers";
import { redirect } from "next/navigation";

import { AppDashboardShell } from "@/components/app-dashboard-shell";
import { auth } from "@/lib/auth";
import { PlaygroundClient } from "./playground-client";

export default async function PlaygroundPage() {
  const requestHeaders = await headers();
  const session = await auth.api.getSession({ headers: requestHeaders });

  if (!session) {
    redirect("/auth");
  }

  const organizations = await auth.api.listOrganizations({ headers: requestHeaders });

  if (!organizations?.length) {
    redirect("/onboarding");
  }

  const organization = organizations[0];
  const { members } = await auth.api.listMembers({
    query: { organizationId: organization.id },
    headers: requestHeaders,
  });
  const role = members.find((member) => member.userId === session.user.id)?.role || "member";

  return (
    <AppDashboardShell active="playground" organizationName={organization.name} user={session.user} role={role}>
      <PlaygroundClient />
    </AppDashboardShell>
  );
}
