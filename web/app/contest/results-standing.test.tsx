// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { RULES, weekPage } from "@/lib/contest-fixture";

import { saveStanding } from "./actions";
import { ContestTabs } from "./contest-tabs";
import { ResultsStanding } from "./results-standing";
import { RulesPanel } from "./rules-panel";

// Results & standing and the rules panel (TASK-073, AC-5): the season, the league standing, this
// week at 0 pts for both at Thu 10:00 PM, the W1–W5 rows, Edit standing, and the read-only rules.
// The Server Actions are mocked; e2e/contest.spec.ts saves a standing and reloads.

vi.mock("./actions", () => ({ addEntry: vi.fn(), removeEntry: vi.fn(), saveStanding: vi.fn() }));
const save = vi.mocked(saveStanding);

beforeEach(() => save.mockReset().mockResolvedValue({ kind: "saved" }));
afterEach(cleanup);

const page = weekPage();

function renderResults() {
  render(
    <ResultsStanding
      contestId={1}
      period={6}
      picks={4}
      results={page.results}
      standing={page.standing}
      games={page.games}
      entries={page.entries}
    />,
  );
}

const cards = () => Array.from(document.querySelectorAll("[data-slot=season-card]")).map((c) => c.textContent);

describe("AC-5: results and standing", () => {
  it("shows the season records, the standing and this week at 0 pts for both", () => {
    renderResults();
    expect(cards()[0]).toContain("You · season");
    expect(cards()[0]).toContain("12-8");
    expect(cards()[1]).toContain("Model top 4 · season");
    expect(cards()[1]).toContain("11-9");
    const standing = document.querySelector("[data-slot=standing]")!;
    expect(standing.textContent).toContain("3rd of 14");
    expect(standing.textContent).toContain("1 pt behind 1st");
    expect(standing.textContent).toContain("Entered by hand");
    const sides = Array.from(document.querySelectorAll("[data-slot=week-side]"));
    expect(sides.map((s) => s.textContent)).toEqual([
      "You0 pts0-0 · 2 pendingOU +7 · BUF −3",
      "Model's top 40 pts0-0 · 4 pendingOU +7 · MISS +3 · OSU −27 · BYU −5.5",
    ]);
  });

  it("lists the weeks W1 to W5 with a total", () => {
    renderResults();
    const rows = Array.from(document.querySelectorAll("[data-slot=week-row]"));
    expect(rows.map((r) => r.textContent)).toEqual([
      "W13-12-2+1",
      "W22-23-1−1",
      "W33-12-2+1",
      "W41-32-2−1",
      "W53-12-2+1",
    ]);
    expect(screen.getByRole("img", { name: /Cumulative wins by week/ })).toBeTruthy();
  });

  it("says so when no results exist yet", () => {
    render(
      <ResultsStanding contestId={1} period={6} picks={4} results={null} standing={null} games={[]} entries={[]} />,
    );
    expect(screen.getByText(/No results yet/)).toBeTruthy();
  });

  it("saves a new standing for this week and closes the form", async () => {
    renderResults();
    fireEvent.click(screen.getByRole("button", { name: "Edit standing" }));
    fireEvent.change(screen.getByLabelText("Place"), { target: { value: "2" } });
    fireEvent.change(screen.getByLabelText("Of"), { target: { value: "14" } });
    fireEvent.change(screen.getByLabelText("Pts back"), { target: { value: "0.5" } });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Save" }));
    });
    expect(save).toHaveBeenCalledWith(1, 6, 2, 14, 0.5);
    expect(screen.queryByLabelText("Place")).toBeNull();
  });

  it("starts from the current standing, and a blank 'Pts back' is not entered", async () => {
    renderResults();
    fireEvent.click(screen.getByRole("button", { name: "Edit standing" }));
    expect((screen.getByLabelText("Place") as HTMLInputElement).value).toBe("3");
    expect((screen.getByLabelText("Of") as HTMLInputElement).value).toBe("14");
    expect((screen.getByLabelText("Pts back") as HTMLInputElement).value).toBe("1");
    fireEvent.change(screen.getByLabelText("Pts back"), { target: { value: "" } });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Save" }));
    });
    expect(save).toHaveBeenCalledWith(1, 6, 3, 14, null);
  });

  it("keeps the form open and says why when the standing isn't saved", async () => {
    save.mockResolvedValue({ kind: "failed", message: "Check the place, the field size and the points back." });
    renderResults();
    fireEvent.click(screen.getByRole("button", { name: "Edit standing" }));
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Save" }));
    });
    expect(screen.getByRole("alert").textContent).toBe("Check the place, the field size and the points back.");
    expect(screen.getByLabelText("Place")).toBeTruthy();
  });
});

describe("AC-5: the rules panel", () => {
  it("lists the contest's rules, read-only, with the plain-English paragraph", () => {
    render(<RulesPanel name="Splash work league" rules={RULES} />);
    const panel = document.querySelector("[data-slot=rules-panel]")!;
    const text = panel.textContent ?? "";
    for (const part of [
      "Splash work league",
      "CFB + NFL",
      "Exactly 4",
      "Each game locks at its kickoff",
      "1 point per correct pick",
      "A push scores 0",
      "This week, in plain English",
    ]) {
      expect(text).toContain(part);
    }
    expect(within(panel as HTMLElement).queryAllByRole("button")).toHaveLength(0);
    expect(panel.querySelector("input, select, textarea")).toBeNull();
  });
});

describe("the tabs", () => {
  it("opens on this week's picks, and the season chip opens Results & standing", () => {
    render(<ContestTabs page={page} period={6} />);
    const tab = (name: string) => screen.getByRole("tab", { name });
    expect(tab("This week's picks").getAttribute("aria-selected")).toBe("true");
    expect(document.getElementById("contest-panel-results")!.hasAttribute("hidden")).toBe(true);
    const chip = document.querySelector("[data-slot=season-chip]")!;
    expect(chip.textContent).toContain("12-8");
    expect(chip.textContent).toContain("11-9");
    expect(chip.textContent).toContain("3rd of 14");
    fireEvent.click(chip);
    expect(tab("Results & standing").getAttribute("aria-selected")).toBe("true");
    expect(document.getElementById("contest-panel-results")!.hasAttribute("hidden")).toBe(false);
    expect(document.getElementById("contest-panel-picks")!.hasAttribute("hidden")).toBe(true);
  });

  it("hides the Rules tab below 1024 px (the form is M8.8)", () => {
    render(<ContestTabs page={page} period={6} />);
    expect(screen.getByRole("tab", { name: "Rules" }).className).toContain("max-lg:hidden");
    fireEvent.click(screen.getByRole("tab", { name: "Rules" }));
    expect(document.getElementById("contest-panel-rules")!.hasAttribute("hidden")).toBe(false);
  });
});
