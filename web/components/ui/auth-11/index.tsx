"use client";

import Image from "next/image";
import Link from "next/link";
import { type FormEvent, useState } from "react";
import { motion, type Variants } from "motion/react";
import { ArrowLeft, ArrowRight, DatabaseZap, Mail } from "lucide-react";

import { authClient } from "@/lib/auth-client";
import { toast } from "@/components/ui/toast";

export default function Auth11({
  callbackURL = "/dashboard",
}: {
  callbackURL?: string;
}) {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [sent, setSent] = useState(false);
  const [pending, setPending] = useState(false);

  const containerVariants: Variants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: { staggerChildren: 0.08, delayChildren: 0.08 },
    },
  };

  const itemVariants: Variants = {
    hidden: { opacity: 0, y: 12 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { type: "spring", stiffness: 300, damping: 24 },
    },
  };

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError("");
    setSent(false);

    const result = await authClient.signIn.magicLink({
      email: email.trim(),
      callbackURL,
      newUserCallbackURL:
        callbackURL === "/dashboard" ? "/onboarding" : callbackURL,
    });

    setPending(false);

    if (result.error) {
      setError(result.error.message || "Could not send magic link");
      return;
    }

    setSent(true);
    toast.add({
      title: "Magic link sent",
      description: "Check your inbox to continue.",
      type: "success",
    });
  }

  return (
    <div className="relative isolate flex min-h-screen w-full flex-col justify-center overflow-hidden bg-blue-500 font-sans text-white antialiased selection:bg-white/20 selection:text-white">
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
            <motion.div
              variants={containerVariants}
              initial="hidden"
              animate="visible"
              className="max-w-2xl 2xl:max-w-7xl"
            >
              <motion.h1
                variants={itemVariants}
                className="mt-5 max-w-2xl text-[clamp(3rem,5.25vw,6rem)] leading-[1.04] font-normal tracking-[-0.055em] text-balance text-white 2xl:max-w-7xl"
              >
                <span className="block">Welcome Back</span>
                <span className="block">To Recall.</span>
              </motion.h1>
              <p className="mt-8 text-sm leading-6 text-white/50">
                Enter your email. We&apos;ll send a secure link. New users
                finish setup after signing in.
              </p>
              <form
                onSubmit={handleSubmit}
                className="flex flex-col gap-4 max-w-[420px] py-8"
              >
                <motion.div
                  variants={itemVariants}
                  className="flex flex-col gap-2"
                >
                  <div className="relative">
                    <Mail className="pointer-events-none absolute top-1/2 left-4 size-4 -translate-y-1/2 text-white/45" />
                    <input
                      id="email"
                      name="email"
                      type="email"
                      required
                      value={email}
                      onChange={(event) => setEmail(event.target.value)}
                      placeholder="you@company.com"
                      className="w-full rounded-full border border-white/15 bg-white/10 px-4 py-3 pl-11 text-sm text-white transition-colors placeholder:text-white/45 focus:border-white/50 focus:bg-white/[0.14] focus:ring-1 focus:ring-white/35 focus:outline-none"
                    />
                  </div>
                </motion.div>

                {error ? <p className="text-sm text-red-300">{error}</p> : null}
                {sent ? (
                  <p className="text-sm text-emerald-300">
                    Check your inbox to continue.
                  </p>
                ) : null}

                <motion.div variants={itemVariants}>
                  <button
                    type="submit"
                    disabled={pending}
                    className="group inline-flex min-h-11 w-full items-center justify-center gap-1 rounded-full bg-zinc-100 px-6 text-sm font-normal text-slate-800 shadow-[inset_0_2px_0_0_rgba(255,255,255,1),inset_0_-1px_0_0_rgba(0,0,0,0.2)] transition-[background-color,color,transform] duration-200 ease-out text-shadow-2xs hover:bg-zinc-200 hover:text-slate-950 active:scale-[0.96] disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {pending ? "Sending..." : "Send magic link"}
                    <ArrowRight className="size-3 transition-transform duration-200 ease-out group-hover:translate-x-0.5" />
                  </button>
                </motion.div>
              </form>
            </motion.div>
          </div>
        </div>
      </div>
    </div>
  );
}
