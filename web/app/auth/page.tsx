import { headers } from "next/headers";
import { redirect } from "next/navigation";

import Auth11 from "@/components/ui/auth-11";
import { auth } from "@/lib/auth";

export default async function AuthPage({
  searchParams,
}: {
  searchParams: Promise<{ callbackURL?: string }>;
}) {
  const session = await auth.api.getSession({ headers: await headers() });
  const { callbackURL = "/dashboard" } = await searchParams;
  const safeCallbackURL = callbackURL.startsWith("/") ? callbackURL : "/dashboard";

  if (session) {
    redirect(safeCallbackURL);
  }

  return <Auth11 callbackURL={safeCallbackURL} />;
}
