import Link from "next/link";
import { headers } from "next/headers";
import { redirect } from "next/navigation";

import { auth } from "@/lib/auth";

export default async function InvitePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const requestHeaders = await headers();
  const session = await auth.api.getSession({ headers: requestHeaders });

  if (!session) {
    redirect(`/auth?callbackURL=${encodeURIComponent(`/invite/${id}`)}`);
  }

  try {
    await auth.api.acceptInvitation({
      body: { invitationId: id },
      headers: requestHeaders,
    });
  } catch {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#0d0b0f] px-6 text-white">
        <div className="w-full max-w-[360px] rounded-[28px] border border-white/10 bg-white/5 p-6 text-center shadow-2xl backdrop-blur">
          <h1 className="text-2xl font-light tracking-tight">Invite unavailable</h1>
          <p className="mt-3 text-sm leading-6 text-white/50">
            This invite is expired, already used, or belongs to another email address.
          </p>
          <Link className="mt-6 inline-flex rounded-full bg-white px-5 py-3 text-sm font-medium text-black" href="/dashboard">
            Go to dashboard
          </Link>
        </div>
      </main>
    );
  }

  redirect("/dashboard");
}
