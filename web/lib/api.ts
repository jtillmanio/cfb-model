import "server-only";

import { auth } from "@/auth";

import { mintApiToken } from "./api-token";
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

async function get<T>(path: string, headers?: HeadersInit): Promise<T> {
  const response = await fetch(apiUrl(path), {
    headers,
    signal: AbortSignal.timeout(TIMEOUT_MS),
  });
  if (!response.ok) {
    throw new Error(`GET /${path} failed with ${response.status}`);
  }
  return (await response.json()) as T;
}

// Every route but health: a fresh short-lived JWT for the signed-in GitHub user, minted per
// request (02 › Auth, D-105). Without a session or a usable secret, nothing is sent.
async function signedGet<T>(path: string): Promise<T> {
  const session = await auth();
  const githubId = session?.user?.id;
  if (!githubId) throw new Error(`GET /${path} needs a signed-in session.`);
  const token = await mintApiToken(githubId);
  return get<T>(path, { Authorization: `Bearer ${token}` });
}

export function getTeams(): Promise<TeamsResponse> {
  return signedGet<TeamsResponse>("api/py/teams");
}

// The only API route outside the auth gate; sign-in calls it to wake the database (TASK-002).
export type HealthResponse = {
  commit: string;
  db_reachable: boolean;
  migration_head: string | null;
};

export function getHealth(): Promise<HealthResponse> {
  return get<HealthResponse>("api/py/health");
}
