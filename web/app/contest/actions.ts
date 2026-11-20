"use server";

import { refresh } from "next/cache";

import {
  addContestEntry,
  addContestStanding,
  confirmContestImport,
  previewContestImport,
  removeContestEntry,
  saveContestAliases,
} from "@/lib/api";
import type { AliasesIn, ImportPreview, ImportRefusal, Side } from "@/lib/contest";

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

// Your picks and standing (TASK-073). The same rules: the API checks the session's user owns the
// contest and the game's lock, so these only check the shape of what the browser sent.

export type WriteResult =
  | { kind: "saved" }
  | { kind: "refused"; code: string; message: string }
  | { kind: "failed"; message: string };

const NOT_SAVED = "Couldn't reach the server. Nothing was saved; try again.";
const REFUSALS = ["locked", "full", "not_on_slate", "no_entry"];

const id = (value: unknown): value is number => Number.isSafeInteger(value) && (value as number) >= 1;

function refusalOfEntry(status: number, body: unknown): WriteResult {
  const d = detail(body);
  if (d.code && REFUSALS.includes(d.code)) {
    return { kind: "refused", code: d.code, message: d.message ?? "That pick can't be changed." };
  }
  return { kind: "failed", message: d.message ?? `The pick wasn't saved (${status}).` };
}

/** Adds your pick on a game's side at its current contest line, or switches the side you had. */
export async function addEntry(contestId: number, gameId: number, side: Side): Promise<WriteResult> {
  if (!id(contestId) || !id(gameId) || (side !== "home" && side !== "away")) {
    return { kind: "failed", message: "That pick can't be saved." };
  }
  try {
    const posted = await addContestEntry(contestId, gameId, side);
    if (!posted.ok) {
      if (posted.status === 409) refresh(); // the screen's picks and locks may be out of date
      return refusalOfEntry(posted.status, posted.body);
    }
  } catch (error) {
    console.error("POST /api/py/contests/{id}/entries failed", error);
    return { kind: "failed", message: NOT_SAVED };
  }
  refresh();
  return { kind: "saved" };
}

/** Adds your picks one after another (the model's top 4), stopping at the first that isn't saved,
 *  with one refresh at the end. `done` is how many were saved before it stopped. */
export async function addEntries(
  contestId: number,
  picks: { game_id: number; side: Side }[],
): Promise<WriteResult & { done: number }> {
  const shaped =
    Array.isArray(picks) &&
    picks.length >= 1 &&
    picks.length <= 20 &&
    picks.every((p) => id(p?.game_id) && (p.side === "home" || p.side === "away"));
  if (!id(contestId) || !shaped) return { kind: "failed", message: "Those picks can't be saved.", done: 0 };
  let done = 0;
  try {
    for (const pick of picks) {
      const posted = await addContestEntry(contestId, pick.game_id, pick.side);
      if (!posted.ok) {
        if (done > 0 || posted.status === 409) refresh();
        return { ...refusalOfEntry(posted.status, posted.body), done };
      }
      done += 1;
    }
  } catch (error) {
    console.error("POST /api/py/contests/{id}/entries failed", error);
    if (done > 0) refresh();
    return { kind: "failed", message: NOT_SAVED, done };
  }
  refresh();
  return { kind: "saved", done };
}

/** Removes your pick on a game. */
export async function removeEntry(contestId: number, gameId: number): Promise<WriteResult> {
  if (!id(contestId) || !id(gameId)) return { kind: "failed", message: "That pick can't be removed." };
  try {
    const deleted = await removeContestEntry(contestId, gameId);
    if (!deleted.ok) {
      if (deleted.status === 409) refresh();
      return refusalOfEntry(deleted.status, deleted.body);
    }
  } catch (error) {
    console.error("DELETE /api/py/contests/{id}/entries/{game} failed", error);
    return { kind: "failed", message: NOT_SAVED };
  }
  refresh();
  return { kind: "saved" };
}

/** Enters your league standing as of now (a new one each time; the page shows the newest). */
export async function saveStanding(
  contestId: number,
  period: number,
  position: number,
  fieldSize: number,
  pointsBehind: number | null,
): Promise<WriteResult> {
  const behind = pointsBehind === null || (Number.isFinite(pointsBehind) && pointsBehind >= 0);
  if (!id(contestId) || !id(period) || !id(position) || !id(fieldSize) || position > fieldSize || !behind) {
    return { kind: "failed", message: "Check the place, the field size and the points back." };
  }
  try {
    const posted = await addContestStanding(contestId, {
      period,
      position,
      field_size: fieldSize,
      points_behind_leader: pointsBehind,
    });
    if (!posted.ok) return { kind: "failed", message: detail(posted.body).message ?? `The standing wasn't saved (${posted.status}).` };
  } catch (error) {
    console.error("POST /api/py/contests/{id}/standings failed", error);
    return { kind: "failed", message: NOT_SAVED };
  }
  refresh();
  return { kind: "saved" };
}
