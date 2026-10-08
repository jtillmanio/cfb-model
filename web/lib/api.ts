import "server-only";

import type { TeamsResponse } from "./teams";

// On Vercel, API_URL is injected by the service binding in vercel.json; locally the API runs
// on :8000 (`pnpm dev`). The browser never calls the API: only server code imports this file.
const LOCAL_API_URL = "http://127.0.0.1:8000";

// Above Neon's worst measured wake (6 s), so a cold start shows the skeleton, not an error (D-097).
const TIMEOUT_MS = 10_000;

function apiUrl(path: string): string {
  const base = process.env.API_URL ?? LOCAL_API_URL;
  return new URL(path, base.endsWith("/") ? base : `${base}/`).toString();
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(apiUrl(path), { signal: AbortSignal.timeout(TIMEOUT_MS) });
  if (!response.ok) {
    throw new Error(`GET /${path} failed with ${response.status}`);
  }
  return (await response.json()) as T;
}

export function getTeams(): Promise<TeamsResponse> {
  return get<TeamsResponse>("api/py/teams");
}
