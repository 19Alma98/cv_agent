import type { DiscoverRequest, DiscoverResponse } from "../types/discover";

function apiBase(): string {
  const base = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "");
  return base && base.length > 0 ? base : "http://127.0.0.1:8000";
}

export async function postDiscover(body: DiscoverRequest): Promise<DiscoverResponse> {
  const res = await fetch(`${apiBase()}/discover`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query: body.query ?? "",
      job_description: body.job_description ?? null,
      top_k: body.top_k ?? 20,
    }),
  });

  if (!res.ok) {
    let message = res.statusText;
    try {
      const data = (await res.json()) as { detail?: unknown };
      if (typeof data.detail === "string") {
        message = data.detail;
      } else if (Array.isArray(data.detail)) {
        message = data.detail.map((d) => JSON.stringify(d)).join("; ");
      }
    } catch {
      /* ignore */
    }
    throw new Error(message || `HTTP ${res.status}`);
  }

  return (await res.json()) as DiscoverResponse;
}
