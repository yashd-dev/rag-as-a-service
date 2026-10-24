import { headers } from "next/headers";
import { redirect } from "next/navigation";

import { auth } from "@/lib/auth";

export async function getDashboardContext() {
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
  let members: Array<{ userId: string; role?: string | null }> = [];
  try {
    const response = await auth.api.listMembers({
      query: { organizationId: organization.id },
      headers: requestHeaders,
    });
    members = response.members;
  } catch (error) {
    console.error("Could not list organization members", error);
  }
  const role = members.find((member) => member.userId === session.user.id)?.role || "member";

  return { requestHeaders, session, organization, role };
}
