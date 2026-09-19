import { headers } from "next/headers";
import { redirect } from "next/navigation";

import { AppDashboardShell } from "@/components/app-dashboard-shell";
import { DashboardPage as AgndexDashboardPage } from "@/components/watermelon/agndex-dashboard/components/agndex/dashboard-page";
import { auth } from "@/lib/auth";

export default async function DashboardPage() {
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
    <AppDashboardShell
      active="overview"
      organizationName={organization.name}
      user={session.user}
      role={role}
    >
      <AgndexDashboardPage />
    </AppDashboardShell>
  );
}
