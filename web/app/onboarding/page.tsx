import Image from "next/image";
import Link from "next/link";
import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { ArrowLeft, ArrowRight, DatabaseZap } from "lucide-react";

import { auth } from "@/lib/auth";

function slugify(value: string) {
  return (
    value
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/(^-|-$)/g, "") || "org"
  );
}

export default async function OnboardingPage() {
  const requestHeaders = await headers();
  const session = await auth.api.getSession({ headers: requestHeaders });

  if (!session) {
    redirect("/auth");
  }

  const organizations = await auth.api.listOrganizations({ headers: requestHeaders });

  if (organizations?.length) {
    redirect("/dashboard");
  }

  async function finishOnboarding(formData: FormData) {
    "use server";

    const requestHeaders = await headers();
    const session = await auth.api.getSession({ headers: requestHeaders });

    if (!session) {
      redirect("/auth");
    }

    const name = String(formData.get("name") || "").trim();
    const organizationName = String(formData.get("organizationName") || "").trim();

    if (name.length < 2 || organizationName.length < 2) {
      redirect("/onboarding");
    }

    await auth.api.updateUser({ body: { name }, headers: requestHeaders });
    await auth.api.createOrganization({
      body: {
        name: organizationName,
        slug: `${slugify(organizationName)}-${session.user.id.slice(0, 8)}`,
      },
      headers: requestHeaders,
    });

    redirect("/dashboard");
  }

  return (
    <main className="relative isolate flex min-h-screen w-full flex-col justify-center overflow-hidden bg-blue-500 font-sans text-white antialiased selection:bg-white/20 selection:text-white">
      <Image
        src="https://assets.watermelon.sh/hero-19-bg.avif"
        alt=""
        fill
        priority
        sizes="100vw"
        className="pointer-events-none absolute inset-0 h-full w-full object-cover object-left sm:object-center"
      />

      <div className="relative z-10 flex min-h-screen w-full flex-col px-6 py-4 sm:px-9 lg:px-12">
        <nav className="flex min-h-10 w-full items-center justify-between">
          <Link
            href="/"
            className="inline-flex min-h-10 items-center gap-2 text-lg font-semibold text-white transition-[opacity,transform] duration-200 ease-out hover:opacity-85 active:scale-[0.96]"
          >
            <span className="inline-flex size-8 items-center justify-center rounded-full border border-white/15 bg-white/10 text-white shadow-sm backdrop-blur-sm">
              <DatabaseZap className="size-4" />
            </span>
            recall
          </Link>

          <Link
            href="/"
            className="group inline-flex min-h-10 items-center gap-2 text-sm font-normal text-white/90 transition-[opacity,transform] duration-200 ease-out hover:opacity-100 active:scale-[0.96]"
          >
            <ArrowLeft className="size-3.5 transition-transform duration-200 ease-out group-hover:-translate-x-0.5" />
            Back
          </Link>
        </nav>

        <div className="flex flex-1 items-center py-12">
          <div className="grid w-full items-center gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(340px,420px)]">
            <div className="max-w-2xl 2xl:max-w-7xl">
              <p className="text-xs leading-none font-medium text-white/95 2xl:text-sm">
                Workspace setup <span aria-hidden="true">-&gt;</span>
              </p>
              <h1 className="mt-5 max-w-2xl text-[clamp(3rem,5.25vw,6rem)] leading-[1.04] font-normal tracking-[-0.055em] text-balance text-white 2xl:max-w-7xl">
                <span className="block">Finish Setup</span>
                <span className="block">For Recall.</span>
              </h1>
              <p className="mt-5 max-w-[31rem] text-[0.78rem] leading-[1.55] font-medium text-pretty text-white/85 2xl:text-lg">
                Add your profile and workspace details before opening the dashboard.
              </p>
            </div>

            <div className="flex w-full justify-center lg:justify-end">
              <div className="w-full max-w-[420px] rounded-[28px] border border-white/15 bg-white/10 p-6 shadow-2xl backdrop-blur-md sm:p-8">
                <div className="mb-7">
                  <h2 className="text-3xl leading-tight font-normal tracking-[-0.055em] text-white md:text-4xl">
                    Create workspace.
                  </h2>
                  <p className="mt-3 text-sm leading-6 text-white/50">
                    Name the user and organization that will own this knowledge base.
                  </p>
                </div>

                <form action={finishOnboarding} className="space-y-4">
                  <label className="block space-y-2 text-xs font-medium text-white/85">
                    <span>Name</span>
                    <input
                      name="name"
                      type="text"
                      required
                      minLength={2}
                      placeholder="Jane Doe"
                      defaultValue={session.user.name}
                      className="w-full rounded-full border border-white/15 bg-white/10 px-4 py-3 text-sm text-white outline-none transition placeholder:text-white/45 focus:border-white/50 focus:bg-white/[0.14] focus:ring-1 focus:ring-white/35"
                    />
                  </label>

                  <label className="block space-y-2 text-xs font-medium text-white/85">
                    <span>Organization</span>
                    <input
                      name="organizationName"
                      type="text"
                      required
                      minLength={2}
                      placeholder="Acme Inc"
                      className="w-full rounded-full border border-white/15 bg-white/10 px-4 py-3 text-sm text-white outline-none transition placeholder:text-white/45 focus:border-white/50 focus:bg-white/[0.14] focus:ring-1 focus:ring-white/35"
                    />
                  </label>

                  <button className="group inline-flex min-h-11 w-full items-center justify-center gap-1 rounded-full bg-zinc-100 px-6 text-sm font-normal text-slate-800 shadow-[inset_0_2px_0_0_rgba(255,255,255,1),inset_0_-1px_0_0_rgba(0,0,0,0.2)] transition-[background-color,color,transform] duration-200 ease-out text-shadow-2xs hover:bg-zinc-200 hover:text-slate-950 active:scale-[0.96]">
                    Finish setup
                    <ArrowRight className="size-3 transition-transform duration-200 ease-out group-hover:translate-x-0.5" />
                  </button>
                </form>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
