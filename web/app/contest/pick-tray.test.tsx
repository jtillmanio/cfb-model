// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ContestEntry, ContestGame } from "@/lib/contest";
import { weekGames, weekPage } from "@/lib/contest-fixture";

import { addEntries, addEntry, removeEntry, type WriteResult } from "./actions";
import { ContestPicks } from "./pick-tray";

// The pick tray and the picks it shares with the slate (TASK-073): what the tray reads (AC-3),
// Use the model's top 4 and Copy picks (AC-3), and a failed save that keeps the picks it had
// (C2c, C2f) and the every-game-locked state (C2d, AC-4). The Server Actions are mocked;
// e2e/contest.spec.ts runs the same taps against the API.

vi.mock("./actions", () => ({ addEntry: vi.fn(), addEntries: vi.fn(), removeEntry: vi.fn() }));
const add = vi.mocked(addEntry);
const addAll = vi.mocked(addEntries);
const remove = vi.mocked(removeEntry);

const SAVED: WriteResult = { kind: "saved" };

beforeEach(() => {
  add.mockReset().mockResolvedValue(SAVED);
  addAll.mockReset().mockResolvedValue({ kind: "saved", done: 0 });
  remove.mockReset().mockResolvedValue(SAVED);
});
afterEach(cleanup);

function renderPicks(games: ContestGame[] = weekGames("thu"), entries: ContestEntry[] = weekPage().entries) {
  render(
    <ContestPicks
      contestId={1}
      contestName="Splash work league"
      period={6}
      picks={4}
      games={games}
      entries={entries}
    />,
  );
}

const tray = () => document.querySelector<HTMLElement>("[data-slot=pick-tray]")!;
const count = () => tray().querySelector("[data-slot=pick-count]")?.textContent;
const slate = (id: number) => document.querySelector<HTMLElement>(`[data-slot=contest-game][data-game="${id}"]`)!;
const tap = async (id: number, name: string) => {
  await act(async () => {
    fireEvent.click(within(slate(id)).getByRole("button", { name }));
  });
};

describe("AC-3: what the tray reads", () => {
  it("reads 'Your picks 2 of 4' with each pick, the line it was locked in at and when", () => {
    renderPicks();
    expect(screen.getByRole("heading", { name: "Your picks 2 of 4" })).toBeTruthy();
    const text = tray().textContent ?? "";
    expect(text).toContain("Locked in at OU +7 · Thu 9:14 PM");
    expect(text).toContain("Locked in at BUF −3 · Thu 9:20 PM");
    expect(text).toContain("1 of 2 match the model");
    const cards = tray().querySelectorAll("[data-slot=tray-card]");
    expect(Array.from(cards).map((c) => c.querySelector("[data-slot=pick-badge]")?.textContent)).toEqual([
      "Model #1",
      "Your call",
    ]);
  });

  it("offers the model's next picks in the open slots and fills them", async () => {
    renderPicks();
    expect(tray().querySelectorAll("[data-slot=open-slot]")).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Add MISS +3" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Add OSU −27" })).toBeTruthy();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Fill 2 open slots with model's picks" }));
    });
    await waitFor(() => expect(addAll).toHaveBeenCalledTimes(1));
    expect(addAll).toHaveBeenCalledWith(1, [
      { game_id: 3, side: "away" },
      { game_id: 2, side: "home" },
    ]);
    expect(add).not.toHaveBeenCalled();
  });

  it("'Use the model's top 4' adds the four from an empty tray, on the model's side", async () => {
    renderPicks(weekGames("thu"), []);
    expect(count()).toBe("0 of 4");
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Use the model's top 4" }));
    });
    await waitFor(() => expect(addAll).toHaveBeenCalledTimes(1));
    expect(addAll.mock.calls[0][1].map((p) => [p.game_id, p.side])).toEqual([
      [5, "home"],
      [3, "away"],
      [2, "home"],
      [6, "home"],
    ]);
  });

  it("shows a tapped pick in the tray at once, before the save answers", async () => {
    let answer: (result: WriteResult) => void = () => {};
    add.mockReturnValue(new Promise<WriteResult>((resolve) => (answer = resolve)));
    renderPicks();
    await tap(3, "MISS +3");
    expect(add).toHaveBeenCalledWith(1, 3, "away");
    expect(count()).toBe("3 of 4");
    expect(tray().textContent).toContain("MISS +3");
    await act(async () => answer(SAVED));
  });

  it("removes on a second tap of the same side, and switches from the tray", async () => {
    renderPicks();
    await tap(5, "OU +7");
    expect(remove).toHaveBeenCalledWith(1, 5);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Switch to TEX −7" }));
    });
    expect(add).toHaveBeenCalledWith(1, 5, "away");
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Remove BUF −3" }));
    });
    expect(remove).toHaveBeenLastCalledWith(1, 7);
  });

  it("copies the picks to the clipboard", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    renderPicks();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Copy picks to enter on Splash" }));
    });
    expect(writeText).toHaveBeenCalledWith(
      "Splash work league · Week 6\n" +
        "OU +7 (Texas vs Oklahoma, Sat 7:30 PM)\n" +
        "BUF −3 (Buffalo @ NY Jets, Sun 1:00 PM)",
    );
    expect(await screen.findByText(/Copied/)).toBeTruthy();
  });

  it("says 'Lock' on no control", () => {
    renderPicks();
    for (const button of screen.getAllByRole("button")) {
      expect(button.getAttribute("aria-label") ?? button.textContent).not.toMatch(/lock/i);
    }
  });

  it("refuses a fifth pick without calling the server", async () => {
    const base = weekPage().entries;
    const four: ContestEntry[] = [
      ...base,
      { ...base[0], id: 13, game_id: 3, side: "away" },
      { ...base[0], id: 14, game_id: 2, side: "home" },
    ];
    renderPicks(weekGames("thu"), four);
    await tap(6, "BYU −5.5");
    expect(add).not.toHaveBeenCalled();
    expect(screen.getByRole("alert").textContent).toContain("Your 4 picks are in");
  });
});

describe("AC-4: a save that fails keeps the picks it had", () => {
  it("shows C2c (C2f's words on a phone) with Retry, and the tray still reads 2 of 4", async () => {
    add.mockResolvedValue({ kind: "failed", message: "Couldn't reach the server." });
    renderPicks();
    await tap(3, "MISS +3");

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Couldn't save MISS +3");
    expect(alert.textContent).toContain("Connection dropped · your picks are unchanged, 2 of 4");
    expect(alert.textContent).toContain("Picks unchanged · 2 of 4");
    expect(count()).toBe("2 of 4");
    expect(tray().querySelectorAll("[data-slot=tray-card]")).toHaveLength(2);
    expect(tray().textContent).not.toContain("MISS +3 ·");

    // Retry runs the same tap again.
    add.mockResolvedValue(SAVED);
    await act(async () => {
      fireEvent.click(within(alert).getByRole("button", { name: "Retry" }));
    });
    expect(add).toHaveBeenCalledTimes(2);
    expect(add).toHaveBeenLastCalledWith(1, 3, "away");
    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
  });

  it("stops a fill at the first pick that isn't saved, and says which, with the picks that were", async () => {
    addAll.mockResolvedValue({ kind: "failed", message: "x", done: 1 });
    renderPicks();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Fill 2 open slots with model's picks" }));
    });
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Couldn't save OSU −27");
    expect(alert.textContent).toContain("your picks are unchanged, 3 of 4");
    expect(within(alert).getByRole("button", { name: "Retry" })).toBeTruthy();
  });

  it("explains a refusal with the server's words and no Retry", async () => {
    add.mockResolvedValue({ kind: "refused", code: "locked", message: "That game has kicked off." });
    renderPicks();
    await tap(3, "MISS +3");
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("That game has kicked off.");
    expect(within(alert).queryByRole("button", { name: "Retry" })).toBeNull();
    expect(count()).toBe("2 of 4");
  });

  it("shows a failed remove as one", async () => {
    remove.mockResolvedValue({ kind: "failed", message: "x" });
    renderPicks();
    await tap(5, "OU +7");
    expect((await screen.findByRole("alert")).textContent).toContain("Couldn't remove OU +7");
    expect(count()).toBe("2 of 4");
  });
});

describe("AC-4: every game locked (C2d)", () => {
  it("keeps your picks as final and offers no way to add", () => {
    renderPicks(weekGames("after"));
    expect(screen.getByRole("heading", { name: "Your picks 2 of 4" })).toBeTruthy();
    expect(tray().textContent).toContain("all games locked, picks are final");
    expect(tray().textContent).toContain("Locked at kickoff · pick is final");
    const slots = Array.from(tray().querySelectorAll("[data-slot=open-slot]"));
    expect(slots.map((s) => s.textContent)).toEqual(["Empty · no games left to pick", "Empty · no games left to pick"]);
    expect(screen.queryByRole("button", { name: /Fill|Use the model|Add /i })).toBeNull();
    expect(document.querySelector("[data-slot=all-locked]")?.textContent).toContain("Every game has kicked off");
    expect(document.querySelector("[data-slot=cutoff]")).toBeNull();
    for (const row of document.querySelectorAll("[data-slot=contest-game]")) {
      for (const button of within(row as HTMLElement).getAllByRole("button")) {
        expect((button as HTMLButtonElement).disabled).toBe(true);
      }
    }
  });
});
