const backendUrl = process.env.BACKEND_URL || "http://localhost:5000";

function failure(code: string, status: number) {
  return Response.json({ error: { message: code.replaceAll("_", " "), type: status < 500 ? "invalid_request_error" : "server_error", code, param: null } }, { status });
}

async function proxy(request: Request, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  const allowed = (request.method === "POST" && path.join("/") === "chat/completions") || (request.method === "GET" && (path.join("/") === "models" || (path.length === 4 && path[0] === "corpora" && path[2] === "passages")));
  if (!allowed || path.some((part) => !/^[A-Za-z0-9_-]+$/.test(part))) return failure("route_not_found", 404);
  const authorization = request.headers.get("authorization");
  if (!authorization?.startsWith("Bearer rag_") || authorization.length > 256) return failure("invalid_api_key", 401);
  let body: string | undefined;
  if (request.method === "POST") {
    if (Number(request.headers.get("content-length")) > 16384) return failure("request_too_large", 413);
    const reader = request.body?.getReader();
    if (!reader) return failure("json_object_required", 400);
    const blocks: Uint8Array[] = [];
    let length = 0;
    while (true) {
      const next = await reader.read();
      if (next.done) break;
      length += next.value.byteLength;
      if (length > 16384) { await reader.cancel(); return failure("request_too_large", 413); }
      blocks.push(next.value);
    }
    const bytes = new Uint8Array(length);
    let offset = 0;
    for (const block of blocks) { bytes.set(block, offset); offset += block.length; }
    try { body = new TextDecoder("utf-8", { fatal: true }).decode(bytes); } catch { return failure("invalid_request", 400); }
  }
  try {
    const upstream = await fetch(`${backendUrl}/v1/${path.map(encodeURIComponent).join("/")}`, {
      method: request.method, body, headers: { Authorization: authorization, "Content-Type": "application/json" },
      cache: "no-store", signal: AbortSignal.any([request.signal, AbortSignal.timeout(900_000)]),
    });
    return new Response(upstream.body, { status: upstream.status, headers: { "Content-Type": upstream.headers.get("content-type") || "application/json", "Cache-Control": "no-store", "X-Accel-Buffering": "no", ...(upstream.headers.get("retry-after") ? { "Retry-After": upstream.headers.get("retry-after")! } : {}) } });
  } catch { return failure("service_unavailable", 503); }
}

export const GET = proxy;
export const POST = proxy;
