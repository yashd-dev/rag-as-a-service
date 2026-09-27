import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { ChevronDown, Copy } from "lucide-react";

import { AppDashboardShell } from "@/components/app-dashboard-shell";
import { Button } from "@/components/ui/button";
import { auth } from "@/lib/auth";

export default async function ApiPage() {
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
    <AppDashboardShell active="api" organizationName={organization.name} user={session.user} role={role}>
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-8 p-4 md:p-8">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">API</h1>
          <p className="text-muted-foreground">Manage credentials for accessing Recall programmatically.</p>
        </div>

        <section className="overflow-hidden rounded-xl border bg-background">
          <div className="flex items-center justify-between border-b px-4 py-4 md:px-6">
            <div className="flex items-center gap-3">
              <h2 className="text-2xl font-medium tracking-tight">Personal API key</h2>
              <span className="rounded-full bg-green-100 px-3 py-1 text-xs font-medium text-green-700">Enabled</span>
            </div>
            <Button variant="outline" className="h-9 gap-2 px-3 font-normal">
              <ChevronDown className="size-4" />
              Actions
            </Button>
          </div>

          <div className="grid gap-6 px-4 py-5 md:grid-cols-[1fr_auto] md:px-6">
            <div className="max-w-2xl text-sm leading-relaxed">
              <p>
                Your Personal API key can access the same set of operations that your role can access. <span className="text-primary">Learn more.</span>
              </p>
              <p className="mt-4">
                <span className="font-semibold">Keep it safe.</span> Your Personal API key is as private and sensitive as a password.
                <br />
                It&apos;s unique to you and should never be disclosed publicly.
              </p>
            </div>

            <div className="flex items-center gap-3 self-start md:self-center">
              <code className="text-sm text-muted-foreground">...DK2-IDzomg</code>
              <Button variant="outline" size="icon" className="size-11 shadow-sm">
                <Copy className="size-4" />
              </Button>
            </div>
          </div>
        </section>
      </div>
    </AppDashboardShell>
  );
}
