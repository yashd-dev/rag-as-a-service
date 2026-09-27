"use client";

import { useState } from "react";
import { ArrowLeft, Check, ChevronDown, Code2, Copy, Database, Plus, X } from "lucide-react";

import { Button } from "@/components/ui/button";

const corpusJson = `{
  "corpusKey": "supreme_court",
  "name": "Supreme Court",
  "description": "Supreme Court Documents",
  "documentsAreQuestions": false,
  "filterAttributes": [
    {
      "name": "lang",
      "level": "part",
      "type": "text",
      "description": "Detected language, as an ISO 639-3 code.",
      "indexed": true
    },
    {
      "name": "is_title",
      "level": "part",
      "type": "boolean",
      "description": "True if the text is a title.",
      "indexed": true
    }
  ]
}`;

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="overflow-hidden rounded-xl border bg-background">
      <div className="flex items-center gap-2 border-b px-4 py-3 font-medium tracking-tight">
        <ChevronDown className="size-4" />
        {title}
      </div>
      <div className="p-4 md:p-6">{children}</div>
    </section>
  );
}

function Field({ label, helper, children }: { label: string; helper?: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-2">
      <span className="text-sm font-medium tracking-tight">{label}</span>
      {helper ? <span className="text-sm text-muted-foreground">{helper}</span> : null}
      {children}
    </label>
  );
}

function FilterRow({ name, type, description }: { name: string; type: string; description: string }) {
  return (
    <div className="grid grid-cols-[1fr_140px_36px] items-center gap-3 border-t py-3 text-sm first:border-t-0">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <code className="rounded-lg bg-secondary px-3 py-2 font-mono text-xs">{name}</code>
          <Button variant="outline" size="icon-sm"><Copy className="size-3.5" /></Button>
        </div>
        <p className="mt-2 text-xs text-muted-foreground">{description}</p>
      </div>
      <span className="text-sm">{type}</span>
      <Button variant="outline" size="icon-sm"><ChevronDown className="size-3.5" /></Button>
    </div>
  );
}

export function DocumentClient() {
  const [mode, setMode] = useState<"empty" | "create">("empty");
  const [jsonOpen, setJsonOpen] = useState(false);

  if (mode === "empty") {
    return (
      <div className="flex min-h-[calc(100svh-4rem)] flex-col">
        <div className="flex h-16 items-center justify-between border-b px-4 md:px-6">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <span>Documents</span>
            <span>/</span>
            <span className="text-foreground">Corpus</span>
          </div>
          <Button onClick={() => setMode("create")} className="h-11 gap-2 px-4 font-normal">
            <Plus className="size-4" />
            Create corpus
          </Button>
        </div>

        <div className="grid flex-1 place-items-center p-6">
          <div className="flex max-w-2xl flex-col items-center text-center">
            <div className="mb-8 grid size-24 place-items-center rounded-full bg-foreground text-background">
              <Database className="size-11" />
            </div>
            <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">A corpus is required before adding documents</h1>
            <p className="mt-4 max-w-xl text-base text-muted-foreground">
              Create a corpus to organize documents, configure retrieval metadata, and ground your assistants in your data.
            </p>
            <div className="mt-10 grid w-full gap-4 sm:grid-cols-2">
              <button className="rounded-xl border bg-card p-5 text-left transition-colors hover:bg-(--card-hover)">
                <h2 className="font-medium tracking-tight">Try a demo corpus</h2>
                <p className="mt-2 text-sm text-muted-foreground">Explore the document flow with sample data.</p>
              </button>
              <button onClick={() => setMode("create")} className="rounded-xl border bg-card p-5 text-left transition-colors hover:bg-(--card-hover)">
                <h2 className="font-medium tracking-tight text-primary">Create your own corpus</h2>
                <p className="mt-2 text-sm text-muted-foreground">Fill your first corpus with PDFs, HTML, or text documents.</p>
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="relative min-h-[calc(100svh-4rem)] overflow-hidden bg-background">
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-7 p-4 md:p-8">
        <button onClick={() => setMode("empty")} className="flex w-fit items-center gap-2 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-4" />
          Back
        </button>

        <div className="flex flex-col gap-5">
          <h1 className="text-2xl font-semibold tracking-tight">What do you want to name this corpus?</h1>
          <div className="grid max-w-2xl gap-5">
            <Field label="Name (required)" helper="Enter a name up to 50 characters long.">
              <input defaultValue="Supreme Court" className="h-11 rounded-lg border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring" />
            </Field>
            <Field label="Key (required)" helper="Enter a key up to 50 characters long. This will be used to uniquely identify the corpus.">
              <input defaultValue="supreme_court" className="h-11 rounded-lg border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-ring" />
            </Field>
          </div>
        </div>

        <div className="flex flex-col gap-5">
          <h2 className="text-2xl font-semibold tracking-tight">Corpus configuration</h2>
          <Field label="Description">
            <textarea defaultValue="Supreme Court Documents" className="min-h-28 rounded-lg border bg-background p-3 text-sm outline-none focus:ring-2 focus:ring-ring" />
          </Field>

          <Section title="Embedding model">
            <p className="text-sm text-muted-foreground">The embedding model used to convert text to vectors.</p>
            <div className="mt-8 flex items-start gap-4 pl-6">
              <span className="mt-1 grid size-4 place-items-center rounded-full border border-primary"><span className="size-2 rounded-full bg-primary" /></span>
              <div>
                <p className="text-sm font-medium tracking-tight">Boomerang (ID: 23111)</p>
                <p className="mt-1 text-sm text-muted-foreground">Optimized for high-quality, cross-lingual retrieval.</p>
              </div>
            </div>
          </Section>

          <Section title="Filter attributes">
            <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
              <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">
                When querying your data, you can filter on specific metadata to narrow your search results. These are called filter attributes. If you&apos;re not sure how to use these yet, the defaults will work fine. <span className="text-primary">Learn more</span>
              </p>
              <Button variant="outline" className="h-11 px-4 font-normal">Add filter attribute</Button>
            </div>
            <div className="mt-7 grid grid-cols-[1fr_140px_36px] gap-3 border-b pb-2 text-sm font-medium">
              <span>Filter</span>
              <span>Type</span>
              <span />
            </div>
            <FilterRow name="part.lang" type="Text" description="Detected language, as an ISO 639-3 code." />
            <FilterRow name="part.is_title" type="Boolean" description="True if the text is a title." />
          </Section>

          <Section title="Advanced options">
            <div className="max-w-2xl">
              <h3 className="font-medium tracking-tight">Treat data as questions</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                By default, Recall will assume the data in this corpus contains answers to questions. Alternatively, you can configure this corpus to contain the questions themselves. This is useful when storing content such as FAQs. <span className="text-primary">Learn more</span>
              </p>
              <div className="mt-7 flex flex-col gap-3 text-sm">
                <label className="flex items-center gap-3"><span className="size-4 rounded-full border" />Treat data as questions</label>
                <label className="flex items-center gap-3"><span className="grid size-4 place-items-center rounded-full border border-primary"><span className="size-2 rounded-full bg-primary" /></span>Treat data as answers (default)</label>
              </div>
              <p className="mt-5 text-sm text-muted-foreground">Custom dimensions aren&apos;t enabled.</p>
            </div>
          </Section>
        </div>

        <div className="flex items-center justify-between pb-10">
          <Button className="h-11 px-5 font-normal">Create corpus</Button>
          <button onClick={() => setJsonOpen(true)} className="flex items-center gap-2 text-sm font-medium text-primary">
            <Code2 className="size-4" />
            Edit JSON
          </button>
        </div>
      </div>

      {jsonOpen ? (
        <div className="absolute inset-0 z-40 flex bg-foreground/45">
          <button aria-label="Close JSON editor" className="flex-1" onClick={() => setJsonOpen(false)} />
          <aside className="flex w-full max-w-2xl flex-col bg-background shadow-xl">
            <div className="flex h-16 items-center justify-between border-b px-6">
              <div className="flex items-center gap-2 font-semibold tracking-tight"><Code2 className="size-4 text-primary" />Edit corpus JSON</div>
              <button onClick={() => setJsonOpen(false)}><X className="size-4" /></button>
            </div>
            <div className="flex-1 p-6">
              <h3 className="font-medium tracking-tight">Corpus JSON</h3>
              <p className="mt-2 text-sm text-muted-foreground">Edit the corpus configuration as JSON.</p>
              <textarea defaultValue={corpusJson} className="mt-4 h-80 w-full rounded-lg border bg-background p-4 font-mono text-sm outline-none focus:ring-2 focus:ring-ring" />
            </div>
            <div className="flex items-center justify-between border-t p-6">
              <Button variant="outline" onClick={() => setJsonOpen(false)} className="h-11 px-5 font-normal">Cancel</Button>
              <Button onClick={() => setJsonOpen(false)} className="h-11 gap-2 px-5 font-normal"><Check className="size-4" />Apply changes</Button>
            </div>
          </aside>
        </div>
      ) : null}
    </div>
  );
}
