import { graphData } from "@/lib/backend";

export async function GET(_request: Request, { params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  return Response.json(await graphData(projectId));
}
