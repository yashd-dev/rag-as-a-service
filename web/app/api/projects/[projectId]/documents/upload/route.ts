import { NextRequest, NextResponse } from "next/server";

import { getDashboardContext } from "@/lib/dashboard-context";

const backendUrl = process.env.BACKEND_URL || "http://localhost:5000";

export async function POST(request: NextRequest, { params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  const { session, organization, role } = await getDashboardContext();
  const formData = await request.formData();
  const response = await fetch(`${backendUrl}/api/projects/${projectId}/documents/upload`, {
    method: "POST",
    headers: {
      "X-Internal-Secret": process.env.BACKEND_INTERNAL_SECRET || "",
      "X-User-Id": session.user.id,
      "X-Organization-Id": organization.id,
      "X-User-Role": role,
    },
    body: formData,
  });

  const text = await response.text();
  return new NextResponse(text, {
    status: response.status,
    headers: {
      "Content-Type": response.headers.get("Content-Type") || "application/json",
    },
  });
}
