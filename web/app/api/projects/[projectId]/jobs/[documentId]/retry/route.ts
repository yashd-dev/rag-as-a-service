import { unstable_rethrow } from "next/navigation";
import { BackendError, backendRequest } from "@/lib/backend";

export async function POST(request: Request, { params }: { params: Promise<{ projectId: string; documentId: string }> }) {
  if (request.headers.get("origin") !== new URL(request.url).origin) return Response.json({ error: "Invalid origin" }, { status: 403 });
  const { projectId, documentId } = await params;
  try {
    return Response.json(await backendRequest(`/api/projects/${encodeURIComponent(projectId)}/jobs/${encodeURIComponent(documentId)}/retry`, { method: "POST" }), { status: 202 });
  } catch (error) {
    unstable_rethrow(error);
    return Response.json({ error: error instanceof BackendError ? error.message : "Retry unavailable" }, { status: error instanceof BackendError ? error.status : 503 });
  }
}
