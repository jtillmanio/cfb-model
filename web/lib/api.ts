import "server-only";

import { auth } from "@/auth";

import type { components } from "./api-types";
import { mintApiToken } from "./api-token";
import type { AliasesIn, AliasesOut, ContestPage, ImportConfirm, ImportIn, ImportPreview } from "./contest";
import { previewUserId } from "./preview";
import type { Slate, SlateWeek } from "./slate";
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

/** A write's answer: its status and JSON body, so a refusal (a 4xx with a `detail`) reaches the
 *  screen. A network failure, a timeout or a 5xx throws, as a read's failure does. */
export type Posted<T> = { ok: true; status: number; body: T } | { ok: false; status: number; body: unknown };

async function signedPost<T>(path: string, payload: unknown): Promise<Posted<T>> {
  const githubId = previewUserId() ?? (await auth())?.user?.id;
  if (!githubId) throw new Error(`POST /${path} needs a signed-in session.`);
  const token = await mintApiToken(githubId);
  const response = await fetch(apiUrl(path), {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal: AbortSignal.timeout(TIMEOUT_MS),
  });
  if (response.status >= 500) throw new Error(`POST /${path} failed with ${response.status}`);
  const body: unknown = await response.json().catch(() => null);
  return response.ok
    ? { ok: true, status: response.status, body: body as T }
    : { ok: false, status: response.status, body };
}

export function getTeams(): Promise<TeamsResponse> {
  return signedGet<TeamsResponse>("api/py/teams");
}

// This Week: the current week's games with the model's numbers and the shell block (TASK-055).
// With no week the API picks the coming week; a stepped week passes season, type and week
// together (TASK-061).
export function getSlate(week?: SlateWeek | null): Promise<Slate> {
  if (!week) return signedGet<Slate>("api/py/slate");
  const query = new URLSearchParams({
    season: String(week.season),
    season_type: week.season_type,
    week: String(week.week),
  });
  return signedGet<Slate>(`api/py/slate?${query}`);
}

// Contest (S-02, TASK-072): the screen's one call, for a contest id or else your first live
// contest (D-175); null when you have none (a 404).
export async function getContest(contestId: number | null): Promise<ContestPage | null> {
  const query = contestId === null ? "" : `?${new URLSearchParams({ contest_id: String(contestId) })}`;
  try {
    return await signedGet<ContestPage>(`api/py/contest${query}`);
  } catch (error) {
    if (error instanceof Error && error.message.endsWith("failed with 404")) return null;
    throw error;
  }
}

// The import's writes (TASK-070, D-172), called only from the Contest page's Server Actions.
export function previewContestImport(contestId: number, body: ImportIn): Promise<Posted<ImportPreview>> {
  return signedPost<ImportPreview>(`api/py/contests/${contestId}/import/preview`, body);
}

export function saveContestAliases(contestId: number, body: AliasesIn): Promise<Posted<AliasesOut>> {
  return signedPost<AliasesOut>(`api/py/contests/${contestId}/aliases`, body);
}

export function confirmContestImport(contestId: number, body: ImportIn): Promise<Posted<ImportConfirm>> {
  return signedPost<ImportConfirm>(`api/py/contests/${contestId}/import/confirm`, body);
}

// The only API route outside the auth gate; sign-in calls it to wake the database (TASK-002).
export type HealthResponse = components["schemas"]["HealthOut"];

export function getHealth(): Promise<HealthResponse> {
  return get<HealthResponse>("api/py/health");
}
