// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ContestEntry, ContestGame } from "@/lib/contest";
import { weekGames, weekPage } from "@/lib/contest-fixture";

import { RankedSlate } from "./ranked-slate";

// The ranked slate (TASK-073): the rows in the response's order with the cutoff under the 4th
// pick (AC-1), the ≠ chip and its filter (AC-2), one tap per side with no "Lock" control (AC-3),
// and a game that has kicked off greyed with its buttons disabled (AC-4).

afterEach(cleanup);

function renderSlate(games: ContestGame[], entries: ContestEntry[] = [], onTap = vi.fn()) {
  render(<RankedSlate games={games} entries={entries} picks={4} onTap={onTap} />);
  return onTap;
}

const rows = () => Array.from(document.querySelectorAll<HTMLElement>("[data-slot=contest-game]"));
const row = (id: number) => document.querySelector<HTMLElement>(`[data-slot=contest-game][data-game="${id}"]`)!;

describe("AC-1: the slate in the response's order, the cutoff and the next best", () => {
  it("draws the games as the response lists them", () => {
    const games = weekGames("thu");
    renderSlate(games);
    expect(rows().map((r) => Number(r.dataset.game))).toEqual(games.map((g) => g.id));
  });

  it("draws the cutoff right under row 4, with 'Next best #5' and its line and cover %", () => {
    renderSlate(weekGames("thu"));
    const cutoff = document.querySelector<HTMLElement>("[data-slot=cutoff]")!;
    expect(cutoff.previousElementSibling).toBe(rows()[3]);
    expect((rows()[3])?.textContent).toContain("BYU");
    expect((cutoff)?.textContent).toContain("Model's top 4");
    expect((cutoff)?.textContent).toContain("Next best #5 ND −17.5 · 55%");
    expect(cutoff.nextElementSibling).toBe(rows()[4]);
  });

  it("labels the cutoff for the open games once a game has kicked off (D-174)", () => {
    renderSlate(weekGames("sat"));
    expect((document.querySelector("[data-slot=cutoff]"))?.textContent).toContain("Model's top 4 · open games");
  });

  it("reads an NFL row as 'No model yet', its gap and the market-implied cover", () => {
    renderSlate(weekGames("thu"));
    const buf = row(7);
    expect((buf)?.textContent).toContain("No model yet");
    expect((buf)?.textContent).toContain("1.5 pts off mkt → BUF");
    expect((buf)?.textContent).toContain("~54%");
    expect((buf)?.textContent).toContain("mkt-implied");
    expect((row(10))?.textContent).toContain("1 pt off mkt → PHI");
    expect((row(9))?.textContent).toContain("No gap to market");
  });

  it("names the side the model likes in the Edge pill, whichever side that is", () => {
    renderSlate(weekGames("thu"));
    const pill = (id: number) => row(id).querySelector<HTMLElement>("[data-slot=badge]")?.textContent;
    // The API's edge is signed (> 0 likes home): MISS and ND are away picks.
    expect([5, 3, 2, 6, 4].map(pill)).toEqual(["+5.7 OU", "+4.4 MISS", "+4.2 OSU", "+3.6 BYU", "+2.4 ND"]);
  });

  it("fills the rank badge for the model's picks and not for the rest", () => {
    renderSlate(weekGames("thu"));
    const badge = (id: number) => within(row(id)).getByText(/^\d+$/, { selector: "[data-slot=rank]" });
    expect(badge(5).className).toContain("bg-edge");
    expect(badge(4).className).not.toContain("bg-edge");
  });
});

describe("AC-2: the ≠ chip and the 'Line ≠ market' filter", () => {
  it("shows the market line under the contest line with a chip: blue when better, orange when worse", () => {
    renderSlate(weekGames("thu"));
    const better = row(5).querySelector<HTMLElement>("[data-slot=line-chip]")!;
    expect((row(5))?.textContent).toContain("mkt −6.5");
    expect((better)?.textContent).toContain("≠ OU +0.5");
    expect(better.dataset.tone).toBe("better");
    expect(better.className).toContain("text-pos");
    const worse = row(3).querySelector<HTMLElement>("[data-slot=line-chip]")!;
    expect((worse)?.textContent).toContain("≠ LSU +0.5");
    expect(worse.dataset.tone).toBe("worse");
    expect(worse.className).toContain("text-neg");
  });

  it("has no chip where the contest line is the market's", () => {
    renderSlate(weekGames("thu"));
    expect(row(9).querySelector("[data-slot=line-chip]")).toBeNull();
    expect((row(9))?.textContent).toContain("mkt −2.5");
  });

  it("counts the flagged rows in the chip and filters to exactly them", () => {
    renderSlate(weekGames("thu"));
    const chip = screen.getByRole("button", { name: /Line ≠ market/ });
    expect((chip)?.textContent).toContain("Line ≠ market 8");
    expect((screen.getByRole("button", { name: /^All/ }))?.textContent).toContain("All 10");
    fireEvent.click(chip);
    expect(rows()).toHaveLength(8);
    expect(rows().every((r) => r.querySelector("[data-slot=line-chip]") !== null)).toBe(true);
    fireEvent.click(chip);
    expect(rows()).toHaveLength(10);
  });
});

describe("AC-3: one tap per side, and no 'Lock' control", () => {
  it("reports the tapped game and side, and marks the picked side as pressed", () => {
    const entries = weekPage().entries; // OU +7 and BUF −3
    const onTap = renderSlate(weekGames("thu"), entries);
    const ou = within(row(5));
    expect((ou.getByRole("button", { name: "OU +7" })).getAttribute("aria-pressed")).toBe("true");
    expect((ou.getByRole("button", { name: "TEX −7" })).getAttribute("aria-pressed")).toBe("false");
    fireEvent.click(ou.getByRole("button", { name: "TEX −7" }));
    expect(onTap).toHaveBeenCalledWith(expect.objectContaining({ id: 5 }), "away");
    fireEvent.click(within(row(3)).getByRole("button", { name: "MISS +3" }));
    expect(onTap).toHaveBeenLastCalledWith(expect.objectContaining({ id: 3 }), "away");
  });

  it("marks the model's side of an open top-4 game with a dot", () => {
    renderSlate(weekGames("thu"));
    expect(row(5).querySelectorAll("[data-slot=model-dot]")).toHaveLength(1);
    expect(within(row(5)).getByRole("button", { name: "OU +7" }).querySelector("[data-slot=model-dot]")).not.toBeNull();
    expect(row(7).querySelector("[data-slot=model-dot]")).toBeNull();
  });

  it("greys the other buttons when the week is full, without disabling the picked ones", () => {
    const base = weekPage().entries;
    const four: ContestEntry[] = [
      ...base,
      { ...base[0], id: 13, game_id: 3, side: "away" },
      { ...base[0], id: 14, game_id: 2, side: "home" },
    ];
    renderSlate(weekGames("thu"), four);
    expect((within(row(6)).getByRole("button", { name: "BYU −5.5" })).getAttribute("data-state")).toBe("full");
    expect((within(row(2)).getByRole("button", { name: "OSU −27" })).getAttribute("data-state")).toBe("selected");
  });

  it("never says 'Lock' on a control", () => {
    renderSlate(weekGames("fri"));
    for (const button of screen.getAllByRole("button")) {
      expect(button.getAttribute("aria-label") ?? button.textContent).not.toMatch(/lock/i);
    }
  });
});

describe("AC-4: a game that has kicked off", () => {
  it("is greyed, reads 'Picks closed' and has its side buttons disabled", () => {
    renderSlate(weekGames("fri"));
    const unlv = row(1);
    expect((unlv).hasAttribute("data-locked")).toBe(true);
    expect((unlv)?.textContent).toContain("Picks closed");
    const buttons = within(unlv).getAllByRole("button");
    expect(buttons.map((b) => b.textContent)).toEqual(["UNLV +10", "BSU −10"]);
    for (const button of buttons) expect((button as HTMLButtonElement).disabled).toBe(true);
    expect((document.querySelector("[data-slot=locked-header]"))?.textContent).toContain("kicked off · can't be picked or changed");
    // The open games come first, the locked one last.
    expect(rows().at(-1)).toBe(unlv);
  });

  it("shows your pick on a locked game instead of 'Picks closed'", () => {
    const entries: ContestEntry[] = [{ ...weekPage().entries[0], game_id: 1, side: "away", line: -10 }];
    renderSlate(weekGames("fri"), entries);
    expect((row(1))?.textContent).toContain("Your pick · UNLV +10");
  });

  it("draws only the locked list, with no cutoff, when every game has kicked off (C2d)", () => {
    renderSlate(weekGames("after"));
    expect(rows()).toHaveLength(10);
    expect(document.querySelector("[data-slot=cutoff]")).toBeNull();
    for (const button of screen.getAllByRole("button", { name: /[+−]|PK/ })) expect((button as HTMLButtonElement).disabled).toBe(true);
  });
});
