"use server";

import { refresh } from "next/cache";

import { confirmContestImport, previewContestImport, saveContestAliases } from "@/lib/api";
import type { AliasesIn, ImportPreview, ImportRefusal } from "@/lib/contest";

// The Contest page's writes (TASK-072). The browser never calls the API (hard rule 5): these run on
// the server and call TASK-070's routes with the signed JWT. The API re-reads the paste on every
// call (D-172), so nothing the browser sends is trusted beyond the text, the week and the names
// the owner picked. A Server Action is a public POST, so each checks its arguments itself, and the
// API checks the session's user owns the contest.

const MAX_TEXT = 200_000; // the API's own limit (contest_import.MAX_TEXT)

export type PreviewResult =
  | { kind: "preview"; preview: ImportPreview }
  | { kind: "refused"; refusal: ImportRefusal }
  | { kind: "failed"; message: string };

export type ConfirmResult =
  | { kind: "confirmed" }
  | { kind: "refused"; refusal: ImportRefusal }
  | { kind: "failed"; message: string };

const UNREACHABLE = "Couldn't reach the server. Nothing was saved; try again.";

function valid(contestId: unknown, period: unknown, text: unknown): string | null {
  if (!Number.isSafeInteger(contestId) || (contestId as number) < 1) return "No contest to paste into.";
  if (!Number.isSafeInteger(period) || (period as number) < 1) return "No week to paste into.";
  if (typeof text !== "string" || text.trim() === "") return "Paste the contest page first.";
  if (text.length > MAX_TEXT) return "That paste is too long to be a contest page.";
  return null;
}

/** A refusal's `detail`: the import's (code, message, rows) or another route's (code, message). */
function detail(body: unknown): { code?: string; message?: string; rows?: unknown } {
  const value = (body as { detail?: unknown } | null)?.detail;
  return typeof value === "object" && value !== null ? (value as { code?: string; message?: string }) : {};
}

function refusalOf(body: unknown): ImportRefusal | null {
  const d = detail(body);
  const codes = ["unparseable", "no_match", "unresolved"];
  return d.code && codes.includes(d.code) && Array.isArray(d.rows) ? (d as ImportRefusal) : null;
}

/** The paste's rows matched to games, with the re-paste diff. Writes nothing. */
export async function previewImport(contestId: number, period: number, text: string): Promise<PreviewResult> {
  const bad = valid(contestId, period, text);
  if (bad) return { kind: "failed", message: bad };
  try {
    const posted = await previewContestImport(contestId, { text, period });
    if (posted.ok) return { kind: "preview", preview: posted.body };
    const refusal = refusalOf(posted.body);
    if (refusal) return { kind: "refused", refusal };
    return { kind: "failed", message: detail(posted.body).message ?? `The paste was refused (${posted.status}).` };
  } catch (error) {
    console.error("POST /api/py/contests/{id}/import/preview failed", error);
    return { kind: "failed", message: UNREACHABLE };
  }
}

/** Saves the picked names as aliases (they're what the confirm matches them by), then the week's
 *  lines as one snapshot, and refreshes the page. A refusal writes no lines. */
export async function confirmImport(
  contestId: number,
  period: number,
  text: string,
  mappings: AliasesIn["mappings"],
): Promise<ConfirmResult> {
  const bad = valid(contestId, period, text);
  if (bad) return { kind: "failed", message: bad };
  const picked = Array.isArray(mappings) ? mappings : [];
  if (
    picked.length > 100 ||
    !picked.every((m) => typeof m?.alias === "string" && m.alias !== "" && Number.isSafeInteger(m.team_id))
  ) {
    return { kind: "failed", message: "Those team picks can't be saved." };
  }
  try {
    if (picked.length > 0) {
      const saved = await saveContestAliases(contestId, { mappings: picked.map(({ alias, team_id }) => ({ alias, team_id })) });
      if (!saved.ok) {
        return { kind: "failed", message: detail(saved.body).message ?? "The team picks couldn't be saved." };
      }
    }
    const posted = await confirmContestImport(contestId, { text, period });
    if (!posted.ok) {
      const refusal = refusalOf(posted.body);
      if (refusal) return { kind: "refused", refusal };
      return { kind: "failed", message: detail(posted.body).message ?? `The slate wasn't saved (${posted.status}).` };
    }
  } catch (error) {
    console.error("POST /api/py/contests/{id}/import/confirm failed", error);
    return { kind: "failed", message: "Couldn't reach the server. The slate wasn't saved; try again." };
  }
  refresh();
  return { kind: "confirmed" };
}
