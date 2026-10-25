import { unstable_rethrow } from "next/navigation";
import { BackendError, listJobs } from "@/lib/backend";

export async function GET(_request: Request, { params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  try {
    return Response.json(await listJobs(projectId), { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    unstable_rethrow(error);
    return Response.json({ error: error instanceof BackendError ? error.message : "Ingestion status unavailable" }, { status: error instanceof BackendError ? error.status : 503 });
  }
}
