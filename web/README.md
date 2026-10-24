This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Grounded corpus playground

`/dashboard/playground` requires a signed-in workspace. Configure the existing web
auth environment and `BACKEND_URL`, with matching `BACKEND_INTERNAL_SECRET` in web
and Flask. Select a corpus, wait for readiness, choose an available retrieval mode,
then submit a question (maximum 1,024 UTF-8 bytes). Each query is independent.

Readiness checks can take up to two minutes on the current full-scan backend. The
Refresh readiness button rechecks capabilities; graph/hybrid stay unavailable
until the backend publishes a verified graph. Query requests have a five-minute
ceiling; errors retain your question. Timeout does not guarantee backend cancellation.

Inline citations open `/dashboard/playground/<projectId>/passages/<chunkId>` in a
new tab, preserving the playground. Source pages use the signed-in workspace and
resolve canonical text through Flask; page numbers appear only when stored in the
source. Used citations and retrieved-but-unused candidates are shown separately.

Frontend regression checks: `bun test tests/rag.test.mjs`, `bun run lint`,
`bunx --no-install tsc --noEmit --incremental false`, `bun run build`.
See [Stage F evidence and remaining gates](tests/stage-f.md).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
