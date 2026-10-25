import { NextRequest, NextResponse } from "next/server";

import { unstable_rethrow } from "next/navigation";
import { BackendError, createDocument } from "@/lib/backend";

export async function POST(request: NextRequest, { params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  if (request.headers.get("origin") !== request.nextUrl.origin) return NextResponse.json({ error: "Invalid origin" }, { status: 403 });
  if (Number(request.headers.get("content-length")) > 100 * 1024 * 1024) return NextResponse.json({ error: "Upload exceeds 100MB request limit" }, { status: 413 });
  try {
    return NextResponse.json(await createDocument(projectId, await request.formData()), { status: 202 });
  } catch (error) {
    unstable_rethrow(error);
    return NextResponse.json({ error: error instanceof BackendError ? error.message : "Upload could not be queued" }, { status: error instanceof BackendError ? error.status : 503 });
  }
}
