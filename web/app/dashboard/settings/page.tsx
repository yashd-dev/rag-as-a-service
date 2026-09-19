import { headers } from "next/headers";
import { redirect } from "next/navigation";

import { AppDashboardShell } from "@/components/app-dashboard-shell";
import { auth } from "@/lib/auth";

const inviteRoles = ["manager", "inviter", "member"] as const;

function canInvite(role: string) {
  return role.split(",").some((item) => ["owner", "manager", "inviter"].includes(item.trim()));
}

function canRemove(role: string) {
  return role.split(",").some((item) => ["owner", "manager"].includes(item.trim()));
}

async function getSessionOrg() {
  const requestHeaders = await headers();
  const session = await auth.api.getSession({ headers: requestHeaders });

  if (!session) {
    redirect("/auth");
  }

  const organizations = await auth.api.listOrganizations({ headers: requestHeaders });

  if (!organizations?.length) {
    redirect("/onboarding");
  }

  return { requestHeaders, session, organization: organizations[0] };
}

export default async function SettingsPage() {
  const { requestHeaders, session, organization } = await getSessionOrg();
  const [{ members }, invitations] = await Promise.all([
    auth.api.listMembers({ query: { organizationId: organization.id }, headers: requestHeaders }),
    auth.api.listInvitations({ query: { organizationId: organization.id }, headers: requestHeaders }),
  ]);
  const currentRole = members.find((member) => member.userId === session.user.id)?.role || "member";

  async function inviteMember(formData: FormData) {
    "use server";

    const { requestHeaders, session, organization } = await getSessionOrg();
    const { members } = await auth.api.listMembers({
      query: { organizationId: organization.id },
      headers: requestHeaders,
    });
    const currentRole = members.find((member) => member.userId === session.user.id)?.role || "member";
    const email = String(formData.get("email") || "").trim();
    const role = String(formData.get("role") || "member") as (typeof inviteRoles)[number];

    if (!canInvite(currentRole) || !inviteRoles.includes(role)) {
      redirect("/dashboard/settings");
    }

    if (role === "manager" && !canRemove(currentRole)) {
      redirect("/dashboard/settings");
    }

    await auth.api.createInvitation({
      body: { email, role, organizationId: organization.id, resend: true },
      headers: requestHeaders,
    });

    redirect("/dashboard/settings");
  }

  async function removeMember(formData: FormData) {
    "use server";

    const { requestHeaders, session, organization } = await getSessionOrg();
    const { members } = await auth.api.listMembers({
      query: { organizationId: organization.id },
      headers: requestHeaders,
    });
    const currentRole = members.find((member) => member.userId === session.user.id)?.role || "member";
    const memberId = String(formData.get("memberId") || "");

    if (!canRemove(currentRole)) {
      redirect("/dashboard/settings");
    }

    await auth.api.removeMember({
      body: { memberIdOrEmail: memberId, organizationId: organization.id },
      headers: requestHeaders,
    });

    redirect("/dashboard/settings");
  }

  return (
    <AppDashboardShell active="settings" organizationName={organization.name} user={session.user} role={currentRole}>
      <div className="mx-auto flex w-full max-w-4xl flex-col gap-8 p-4 md:p-8">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
          <p className="text-muted-foreground">Manage account, workspace, and members.</p>
        </div>

        <div className="grid gap-3 md:grid-cols-3">
          <div className="rounded-xl bg-card p-4">
            <p className="text-xs text-muted-foreground">Name</p>
            <p className="mt-2 truncate text-sm font-medium">{session.user.name || "Unnamed"}</p>
          </div>
          <div className="rounded-xl bg-card p-4">
            <p className="text-xs text-muted-foreground">Email</p>
            <p className="mt-2 truncate text-sm font-medium">{session.user.email}</p>
          </div>
          <div className="rounded-xl bg-card p-4">
            <p className="text-xs text-muted-foreground">Organization</p>
            <p className="mt-2 truncate text-sm font-medium">{organization.name}</p>
          </div>
        </div>

        <section id="members" className="flex flex-col gap-5">
          <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
            <div>
              <h2 className="font-medium">Members</h2>
              <p className="mt-1 text-sm text-muted-foreground">Invite people and manage workspace access.</p>
            </div>

            {canInvite(currentRole) ? (
              <form action={inviteMember} className="flex w-full flex-col gap-2 md:w-auto md:min-w-[360px]">
                <div className="flex gap-2">
                  <input
                    name="email"
                    type="email"
                    required
                    placeholder="teammate@company.com"
                    className="h-11 flex-1 rounded-lg border bg-secondary px-3 text-sm outline-none placeholder:text-muted-foreground focus:ring-2 focus:ring-ring"
                  />
                  <select
                    name="role"
                    defaultValue="member"
                    className="h-11 rounded-lg border bg-secondary px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
                  >
                    <option value="manager">Add + remove</option>
                    <option value="inviter">Add only</option>
                    <option value="member">Use only</option>
                  </select>
                </div>
                <button className="h-11 rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground">
                  Send invite
                </button>
              </form>
            ) : null}
          </div>

          <div className="overflow-hidden rounded-xl bg-card">
            {members.map((member) => (
              <div key={member.id} className="grid grid-cols-[1fr_120px_90px] items-center gap-3 border-b px-4 py-3 last:border-b-0">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{member.user.name || "Unnamed"}</p>
                  <p className="truncate text-xs text-muted-foreground">{member.user.email}</p>
                </div>
                <span className="text-sm text-muted-foreground">{member.role}</span>
                {canRemove(currentRole) && member.userId !== session.user.id ? (
                  <form action={removeMember}>
                    <input type="hidden" name="memberId" value={member.id} />
                    <button className="rounded-lg px-3 py-2 text-xs text-destructive hover:bg-destructive/10">
                      Remove
                    </button>
                  </form>
                ) : null}
              </div>
            ))}
          </div>
        </section>

        <section className="flex flex-col gap-3">
          <h2 className="font-medium">Pending invites</h2>
          <div className="rounded-xl bg-card">
            {invitations?.length ? (
              invitations.map((invite) => (
                <div key={invite.id} className="flex items-center justify-between border-b px-4 py-3 text-sm last:border-b-0">
                  <span>{invite.email}</span>
                  <span className="text-muted-foreground">{invite.role}</span>
                </div>
              ))
            ) : (
              <p className="px-4 py-3 text-sm text-muted-foreground">No pending invites.</p>
            )}
          </div>
        </section>
      </div>
    </AppDashboardShell>
  );
}
