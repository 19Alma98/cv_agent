import type { DiscoverResponse } from "./types/discover";

export const DISCOVER_REPORT_KEY = "cv_agent_discover_report_v1";

export function saveDiscoverReport(data: DiscoverResponse): void {
  sessionStorage.setItem(DISCOVER_REPORT_KEY, JSON.stringify(data));
}

export function loadDiscoverReport(): DiscoverResponse | null {
  const raw = sessionStorage.getItem(DISCOVER_REPORT_KEY);
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as DiscoverResponse;
  } catch {
    return null;
  }
}
