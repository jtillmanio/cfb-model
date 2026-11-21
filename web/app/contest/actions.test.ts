import { beforeEach, describe, expect, it, vi } from "vitest";

import { addContestEntry, addContestStanding, removeContestEntry } from "@/lib/api";

import { addEntries, addEntry, removeEntry, saveStanding } from "./actions";

// The pick and standing Server Actions (TASK-073): each is a public POST, so it checks the shape
// of what it was sent before calling the API, maps a refusal to words, and refreshes the page
// only when something may have changed. The API client and the refresh are mocked.

vi.mock("@/lib/api", () => ({
  addContestEntry: vi.fn(),
  addContestStanding: vi.fn(),
  confirmContestImport: vi.fn(),
  previewContestImport: vi.fn(),
  removeContestEntry: vi.fn(),
  saveContestAliases: vi.fn(),
}));
const refresh = vi.hoisted(() => vi.fn());
vi.mock("next/cache", () => ({ refresh }));

const add = vi.mocked(addContestEntry);
const remove = vi.mocked(removeContestEntry);
const standing = vi.mocked(addContestStanding);

const OK = { ok: true, status: 200, body: {} } as never;
const refused = (status: number, code: string, message: string) => ({ ok: false, status, body: { detail: { code, message } } }) as never;

beforeEach(() => {
  vi.resetAllMocks();
  vi.spyOn(console, "error").mockImplementation(() => {});
});

describe("addEntry and removeEntry", () => {
  it("rejects a malformed call without calling the API", async () => {
    for (const args of [
      [0, 3, "home"],
      [1.5, 3, "home"],
      [1, -3, "home"],
      [1, 3, "middle"],
      [Number.NaN, 3, "away"],
    ] as const) {
      expect((await addEntry(...(args as unknown as Parameters<typeof addEntry>))).kind).toBe("failed");
    }
    expect((await removeEntry(1, 0)).kind).toBe("failed");
    expect(add).not.toHaveBeenCalled();
    expect(remove).not.toHaveBeenCalled();
    expect(refresh).not.toHaveBeenCalled();
  });

  it("saves, then refreshes the page", async () => {
    add.mockResolvedValue(OK);
    expect(await addEntry(7, 3, "away")).toEqual({ kind: "saved" });
    expect(add).toHaveBeenCalledWith(7, 3, "away");
    expect(refresh).toHaveBeenCalledTimes(1);
  });

  it("turns a locked or full refusal into its words, and refreshes so the screen catches up", async () => {
    add.mockResolvedValue(refused(409, "locked", "That game has kicked off."));
    expect(await addEntry(7, 3, "away")).toEqual({ kind: "refused", code: "locked", message: "That game has kicked off." });
    expect(refresh).toHaveBeenCalledTimes(1);
    add.mockResolvedValue(refused(409, "full", "Week 6 already has 4 picks."));
    expect((await addEntry(7, 4, "home")).kind).toBe("refused");
  });

  it("calls an unreadable failure a failure, and a network error one that wrote nothing", async () => {
    add.mockResolvedValue({ ok: false, status: 422, body: null } as never);
    expect(await addEntry(7, 3, "away")).toEqual({ kind: "failed", message: "The pick wasn't saved (422)." });
    add.mockRejectedValue(new Error("timeout"));
    expect((await addEntry(7, 3, "away")).kind).toBe("failed");
    remove.mockRejectedValue(new Error("timeout"));
    expect((await removeEntry(7, 3)).kind).toBe("failed");
    expect(refresh).not.toHaveBeenCalled();
  });

  it("removes a pick, and says when there was none", async () => {
    remove.mockResolvedValue({ ok: true, status: 204, body: null } as never);
    expect(await removeEntry(7, 3)).toEqual({ kind: "saved" });
    remove.mockResolvedValue(refused(404, "no_entry", "No pick on that game."));
    expect(await removeEntry(7, 3)).toEqual({ kind: "refused", code: "no_entry", message: "No pick on that game." });
  });
});

describe("addEntries (Use the model's top 4)", () => {
  const picks = [
    { game_id: 5, side: "home" as const },
    { game_id: 3, side: "away" as const },
    { game_id: 2, side: "home" as const },
  ];

  it("saves every pick in order, with one refresh", async () => {
    add.mockResolvedValue(OK);
    expect(await addEntries(7, picks)).toEqual({ kind: "saved", done: 3 });
    expect(add.mock.calls.map(([, game, side]) => [game, side])).toEqual([
      [5, "home"],
      [3, "away"],
      [2, "home"],
    ]);
    expect(refresh).toHaveBeenCalledTimes(1);
  });

  it("stops at the first pick that is refused and says how many were saved", async () => {
    add.mockResolvedValueOnce(OK).mockResolvedValueOnce(refused(409, "full", "Week 6 already has 4 picks."));
    expect(await addEntries(7, picks)).toEqual({
      kind: "refused",
      code: "full",
      message: "Week 6 already has 4 picks.",
      done: 1,
    });
    expect(add).toHaveBeenCalledTimes(2);
    expect(refresh).toHaveBeenCalledTimes(1);
  });

  it("refreshes after a network failure only if some pick was saved", async () => {
    add.mockRejectedValue(new Error("timeout"));
    expect(await addEntries(7, picks)).toMatchObject({ kind: "failed", done: 0 });
    expect(refresh).not.toHaveBeenCalled();
    add.mockReset().mockResolvedValueOnce(OK).mockRejectedValue(new Error("timeout"));
    expect(await addEntries(7, picks)).toMatchObject({ kind: "failed", done: 1 });
    expect(refresh).toHaveBeenCalledTimes(1);
  });

  it("rejects an empty, oversized or malformed list without calling the API", async () => {
    expect((await addEntries(7, [])).kind).toBe("failed");
    expect((await addEntries(7, Array.from({ length: 21 }, () => picks[0]))).kind).toBe("failed");
    expect((await addEntries(7, [{ game_id: 0, side: "home" }])).kind).toBe("failed");
    expect((await addEntries(7, [{ game_id: 2, side: "up" as never }])).kind).toBe("failed");
    expect(add).not.toHaveBeenCalled();
  });
});

describe("saveStanding", () => {
  it("saves a standing for the week and refreshes", async () => {
    standing.mockResolvedValue(OK);
    expect(await saveStanding(7, 6, 3, 14, 1)).toEqual({ kind: "saved" });
    expect(standing).toHaveBeenCalledWith(7, { period: 6, position: 3, field_size: 14, points_behind_leader: 1 });
    expect(await saveStanding(7, 6, 3, 14, null)).toEqual({ kind: "saved" });
    expect(standing).toHaveBeenLastCalledWith(7, { period: 6, position: 3, field_size: 14, points_behind_leader: null });
    expect(refresh).toHaveBeenCalledTimes(2);
  });

  it("refuses a place past the field, a zero place and negative points back, without calling the API", async () => {
    for (const args of [
      [7, 6, 15, 14, null],
      [7, 6, 0, 14, null],
      [7, 6, 3, 14, -1],
      [7, 6, Number.NaN, 14, null],
      [7, 6, 3, 14, Number.NaN],
    ] as const) {
      const [contest, period, place, field, behind] = args;
      expect((await saveStanding(contest, period, place, field, behind)).kind).toBe("failed");
    }
    expect(standing).not.toHaveBeenCalled();
    expect(refresh).not.toHaveBeenCalled();
  });

  it("says so when the API refuses it", async () => {
    standing.mockResolvedValue({ ok: false, status: 422, body: { detail: [] } } as never);
    expect(await saveStanding(7, 6, 3, 14, 0.25)).toEqual({ kind: "failed", message: "The standing wasn't saved (422)." });
    expect(refresh).not.toHaveBeenCalled();
  });
});
