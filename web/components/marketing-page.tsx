import Link from 'next/link';
import { ArrowLeft, DatabaseZap } from 'lucide-react';

interface Row {
  label: string;
  detail: string;
  value?: string;
}

interface MarketingPageProps {
  eyebrow: string;
  title: string;
  description: string;
  rows: Row[];
}

export default function MarketingPage({
  eyebrow,
  title,
  description,
  rows,
}: MarketingPageProps) {
  return (
    <main className="min-h-screen bg-blue-500 px-6 py-4 font-sans text-white antialiased sm:px-9 lg:px-12">
      <nav className="mx-auto flex min-h-10 w-full max-w-3xl items-center justify-between 2xl:max-w-4xl">
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

      <section className="mx-auto flex min-h-[calc(100vh-4.5rem)] w-full max-w-3xl flex-col justify-center py-16 2xl:max-w-4xl">
        <p className="text-xs leading-none font-medium text-white/95 2xl:text-sm">
          {eyebrow} <span aria-hidden="true">-&gt;</span>
        </p>
        <h1 className="mt-5 text-[clamp(3rem,5.25vw,6rem)] leading-[1.04] font-normal tracking-[-0.055em] text-balance text-white">
          {title}
        </h1>
        <p className="mt-5 max-w-2xl text-[0.9rem] leading-[1.65] font-medium text-pretty text-white/85 2xl:text-lg">
          {description}
        </p>

        <div className="mt-10 overflow-hidden rounded-[28px] border border-white/15 bg-white/10 shadow-2xl backdrop-blur-md">
          {rows.map((row) => (
            <div
              key={row.label}
              className="grid gap-2 border-b border-white/15 px-5 py-5 last:border-b-0 sm:grid-cols-[12rem_1fr_auto] sm:items-center sm:px-6"
            >
              <div className="text-sm font-medium text-white">{row.label}</div>
              <div className="text-sm leading-6 text-white/75">{row.detail}</div>
              {row.value ? (
                <div className="text-sm font-medium text-white/90">{row.value}</div>
              ) : null}
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
