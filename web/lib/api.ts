import "server-only";

import { auth } from "@/auth";

import type { components } from "./api-types";
import { mintApiToken } from "./api-token";
import { previewUserId } from "./preview";
import type { Slate } from "./slate";
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
// request (02 › Auth, D-105). On a Vercel preview that user is the allowlisted one, session or
// not (D-153). Without a session or a usable secret, nothing is sent.
async function signedGet<T>(path: string): Promise<T> {
  const githubId = previewUserId() ?? (await auth())?.user?.id;
  if (!githubId) throw new Error(`GET /${path} needs a signed-in session.`);
  const token = await mintApiToken(githubId);
  return get<T>(path, { Authorization: `Bearer ${token}` });
}

export function getTeams(): Promise<TeamsResponse> {
  return signedGet<TeamsResponse>("api/py/teams");
}

// This Week: the current week's games with the model's numbers and the shell block (TASK-055).
// With no query the API picks the coming week; a week step (a later task) passes season, type, week.
export function getSlate(): Promise<Slate> {
  return signedGet<Slate>("api/py/slate");
}

// The only API route outside the auth gate; sign-in calls it to wake the database (TASK-002).
export type HealthResponse = components["schemas"]["HealthOut"];

export function getHealth(): Promise<HealthResponse> {
  return get<HealthResponse>("api/py/health");
}
