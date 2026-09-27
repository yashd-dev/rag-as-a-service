"use client";

import { useState } from "react";
import { ChevronDown, Code2, Copy, PanelRight, Plus, Zap } from "lucide-react";

import { Button } from "@/components/ui/button";
import { MonacoCodeEditor } from "./monaco-code-editor";

const snippets = {
  python: `from groq import Groq

client = Groq()
completion = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[
        {"role": "system", "content": "You are a good boy"},
        {"role": "assistant", "content": "Who are you?"},
        {"role": "user", "content": ""}
    ],
    temperature=1,
    max_completion_tokens=2048,
    reasoning_effort="medium",
    stream=True
)

for chunk in completion:
    print(chunk.choices[0].delta.content or "", end="")`,
  javascript: `import Groq from "groq-sdk";

const client = new Groq({ apiKey: process.env.GROQ_API_KEY });

const completion = await client.chat.completions.create({
  model: "openai/gpt-oss-120b",
  messages: [
    { role: "system", content: "You are a good boy" },
    { role: "assistant", content: "Who are you?" },
    { role: "user", content: "" }
  ],
  temperature: 1,
  max_completion_tokens: 2048,
  reasoning_effort: "medium",
  stream: true
});

for await (const chunk of completion) {
  process.stdout.write(chunk.choices[0]?.delta?.content || "");
}`,
  shell: `curl https://api.groq.com/openai/v1/chat/completions \\
  -H "Authorization: Bearer $GROQ_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "openai/gpt-oss-120b",
    "messages": [
      {"role": "system", "content": "You are a good boy"},
      {"role": "assistant", "content": "Who are you?"},
      {"role": "user", "content": ""}
    ],
    "temperature": 1,
    "max_completion_tokens": 2048,
    "reasoning_effort": "medium",
    "stream": true
  }'`,
} as const;

const languageLabels = {
  python: "Python",
  javascript: "JavaScript",
  shell: "cURL",
} as const;

type Language = keyof typeof snippets;

function Toggle({ checked, onClick }: { checked: boolean; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className={`flex h-6 w-11 items-center rounded-full p-0.5 transition-colors ${checked ? "bg-primary" : "bg-border"}`}>
      <span className={`size-5 rounded-full bg-white shadow-sm transition-transform ${checked ? "translate-x-5" : "translate-x-0"}`} />
    </button>
  );
}

function ParameterRow({ label, value, position }: { label: string; value: string; position: string }) {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm font-medium tracking-tight">{label}</span>
        <div className="rounded-lg border bg-background px-3 py-2 text-sm text-muted-foreground">{value}</div>
      </div>
      <div className="relative h-2 rounded-full bg-border">
        <div className="absolute top-1/2 size-4 -translate-y-1/2 rounded-full border border-foreground bg-background shadow-sm" style={{ left: position }} />
      </div>
    </div>
  );
}

export function PlaygroundClient() {
  const [showCode, setShowCode] = useState(true);
  const [showParameters, setShowParameters] = useState(true);
  const [language, setLanguage] = useState<Language>("python");
  const [stream, setStream] = useState(true);
  const [jsonMode, setJsonMode] = useState(false);
  const [browserSearch, setBrowserSearch] = useState(false);
  const [codeInterpreter, setCodeInterpreter] = useState(false);

  return (
    <div className="flex min-h-[calc(100svh-4rem)] flex-col bg-background lg:flex-row">
      <section className="flex min-h-[720px] flex-1 flex-col border-border lg:border-r">
        <div className="flex h-16 items-center justify-between border-b px-4 md:px-6">
          <h1 className="text-2xl font-semibold tracking-tight">Playground</h1>
        </div>

        <div className="flex flex-1 flex-col gap-4 p-4 md:p-6">
          <div className="rounded-xl bg-card p-5 transition-colors hover:bg-(--card-hover)">
            <div className="mb-5 flex items-center justify-between text-xs font-medium uppercase tracking-wide text-muted-foreground">
              <span>System</span>
              <ChevronDown className="size-4" />
            </div>
            <p className="text-sm tracking-tight">You are a good boy</p>
          </div>

          <div className="rounded-xl bg-card p-5 transition-colors hover:bg-(--card-hover)">
            <p className="mb-5 text-xs font-medium uppercase tracking-wide text-muted-foreground">Assistant</p>
            <p className="text-sm tracking-tight">Who are you?</p>
          </div>

          <div className="rounded-xl bg-background p-5">
            <p className="mb-4 text-xs font-medium uppercase tracking-wide text-muted-foreground">Assistant</p>
            <div className="mb-4 flex items-center gap-3 text-sm text-muted-foreground">
              <ChevronDown className="size-4 rotate-180" />
              <span>Reasoning</span>
            </div>
            <p className="mb-5 border-l-4 border-border pl-5 text-sm leading-relaxed text-muted-foreground">
              The user: &quot;You are a good boy&quot;. The system says we are ChatGPT. The user says &quot;Who are you?&quot; We should respond as ChatGPT, introduce ourselves. No policy violation. Provide friendly answer.
            </p>
            <p className="max-w-2xl text-sm leading-relaxed tracking-tight">
              I&apos;m ChatGPT, an AI language model created by OpenAI. I&apos;m here to help answer your questions, brainstorm ideas, explain concepts, or just chat-whatever you need. How can I assist you today?
            </p>
          </div>

          <div className="rounded-xl bg-card p-5 transition-colors hover:bg-(--card-hover)">
            <p className="mb-5 text-xs font-medium uppercase tracking-wide text-muted-foreground">User</p>
            <p className="text-sm text-muted-foreground">Enter user message...</p>
          </div>

          <div className="mt-auto flex items-end justify-between gap-4 pt-8">
            <div className="flex gap-2">
              <Button variant="outline" size="icon" className="size-11"><Plus className="size-4" /></Button>
              <Button variant="outline" className="h-11 px-4 font-normal">Clear</Button>
            </div>
            <div className="hidden items-center gap-3 text-sm italic text-muted-foreground sm:flex">
              <span>Latency: 414 ms</span>
              <Zap className="size-5 fill-primary text-primary" />
              <span>Tokens/s: 239</span>
            </div>
            <Button className="h-11 rounded-full px-6 font-normal shadow-[0_0_0_3px_color-mix(in_oklab,var(--primary)_18%,transparent)]">
              Submit <span className="ml-2 text-primary-foreground/70">Ctrl + ↵</span>
            </Button>
          </div>
        </div>
      </section>

      {showCode ? (
        <section className="flex min-h-[720px] min-w-0 flex-1 flex-col border-border bg-background lg:border-r">
          <div className="flex h-16 items-center gap-3 border-b px-4 md:px-6">
            <div className="min-w-0 flex-1 rounded-lg border bg-secondary px-4 py-3 text-sm font-medium tracking-tight">openai/gpt-oss-120b</div>
            <Button variant="outline" size="icon" className="size-11"><Copy className="size-4" /></Button>
            <Button variant="outline" onClick={() => setShowCode(false)} className="h-11 gap-2 px-4 font-normal"><Code2 className="size-4" />Hide code</Button>
          </div>
          <div className="flex items-center justify-between border-b px-4 py-3 text-sm text-muted-foreground md:px-6">
            <select value={language} onChange={(event) => setLanguage(event.target.value as Language)} className="rounded-lg border bg-background px-3 py-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-ring">
              {Object.entries(languageLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
            <span className="flex items-center gap-2"><Copy className="size-4" /> Copy</span>
          </div>
          <div className="min-h-[520px] flex-1 overflow-hidden bg-card">
            <MonacoCodeEditor language={language} value={snippets[language]} />
          </div>
        </section>
      ) : null}

      {showParameters ? (
        <aside className="w-full shrink-0 bg-background p-6 lg:w-[300px]">
          <div className="mb-10 flex items-center justify-between text-xs font-medium uppercase tracking-wide text-muted-foreground">
            <span>Parameters</span>
            <button type="button" onClick={() => setShowParameters(false)}><PanelRight className="size-4" /></button>
          </div>
          <div className="space-y-8">
            <ParameterRow label="Temperature" value="1" position="50%" />
            <ParameterRow label="Max Completion Tokens" value="2048" position="3%" />
            <div className="flex items-center justify-between gap-4">
              <span className="text-sm font-medium tracking-tight">Reasoning</span>
              <div className="flex min-w-36 items-center justify-between rounded-lg border bg-secondary px-4 py-3 text-sm">medium <ChevronDown className="size-4 text-muted-foreground" /></div>
            </div>
            <div className="flex items-center justify-between"><span className="text-sm font-medium tracking-tight">Stream</span><Toggle checked={stream} onClick={() => setStream((value) => !value)} /></div>
            <div className="flex items-center justify-between"><span className="text-sm font-medium tracking-tight">JSON Mode</span><Toggle checked={jsonMode} onClick={() => setJsonMode((value) => !value)} /></div>
            <div className="space-y-5 border-t pt-5">
              <p className="text-sm text-muted-foreground">Built-in tools</p>
              <div className="flex items-center justify-between"><span className="text-sm">Browser Search</span><Toggle checked={browserSearch} onClick={() => setBrowserSearch((value) => !value)} /></div>
              <div className="flex items-center justify-between"><span className="text-sm">Code Interpreter</span><Toggle checked={codeInterpreter} onClick={() => setCodeInterpreter((value) => !value)} /></div>
            </div>
            <div className="space-y-5 border-t pt-5">
              <p className="text-sm text-muted-foreground">Custom function tools</p>
              <Button variant="outline" className="mx-auto flex h-11 gap-3 px-5 font-normal"><Plus className="size-4" />Add Function</Button>
            </div>
            <div className="space-y-5 border-t pt-5">
              <p className="text-sm text-muted-foreground">MCP Servers</p>
              <Button variant="outline" className="mx-auto flex h-11 gap-3 px-5 font-normal"><Plus className="size-4" />Add MCP Server</Button>
            </div>
          </div>
        </aside>
      ) : null}

      {!showCode || !showParameters ? (
        <div className="fixed bottom-6 right-6 flex gap-2">
          {!showCode ? <Button variant="outline" onClick={() => setShowCode(true)} className="h-11 gap-2 bg-background px-4 font-normal"><Code2 className="size-4" />Show code</Button> : null}
          {!showParameters ? <Button variant="outline" onClick={() => setShowParameters(true)} className="h-11 gap-2 bg-background px-4 font-normal"><PanelRight className="size-4" />Parameters</Button> : null}
        </div>
      ) : null}
    </div>
  );
}
