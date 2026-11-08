// @vitest-environment jsdom
import { cleanup, render, screen, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Shell } from "@/lib/shell";

import { AppShell } from "./app-shell";

// next/link needs the app router mounted; a plain anchor is enough to read hrefs here.
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

// The week picker is a client island that uses the router.
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

afterEach(cleanup);

const SHELL: Shell = {
  season: 2026,
  season_type: "regular",
  week: 6,
  model: { name: "v1", version: "1.0" },
  record: { wins: 32, losses: 24, pushes: 1, win_pct: 57.14, units: 4.62, avg_clv: 0.94 },
  record_label: "live",
  lines_updated_at: "2026-10-10T13:00:00+00:00",
  stale: false,
  picks: 9,
  next_season: null,
  next_week: null,
};

function renderShell(shell: Shell | null, state: "ready" | "loading" | "error" = "ready") {
  return render(
    <AppShell active="teams" path="/teams" shell={shell} state={state}>
      <main>content</main>
    </AppShell>,
  );
}

describe("stale banner (AC-5)", () => {
  it("reads 'Lines last updated <time> ET' with Refresh when the lines are stale", () => {
    renderShell({ ...SHELL, stale: true });
    const banner = screen.getByRole("status", { name: "Lines last updated Sat 9:00 AM ET" });
    expect(banner.textContent).toContain("Lines last updated Sat 9:00 AM ET");
    const refresh = within(banner).getByRole("link", { name: "Refresh" });
    expect(refresh.getAttribute("href")).toBe("/teams");
    // D-096: no saved copies, so none of the design's saved-copy wording.
    expect(banner.textContent).not.toMatch(/saved copy|offline copy|couldn't reach/i);
  });

  it("draws no banner when the lines are fresh", () => {
    renderShell(SHELL);
    expect(screen.queryByText(/Lines last updated/)).toBeNull();
  });

  it("draws no banner while loading or after an error", () => {
    renderShell(null, "loading");
    expect(screen.queryByText(/Lines last updated/)).toBeNull();
    cleanup();
    renderShell(null, "error");
    expect(screen.queryByText(/Lines last updated/)).toBeNull();
  });
});

describe("app shell", () => {
  it("marks the active screen and links the track record to Performance", () => {
    renderShell(SHELL);
    const sidebar = screen.getByRole("navigation", { name: "Main" });
    const teams = within(sidebar).getByRole("link", { name: "Teams" });
    expect(teams.getAttribute("aria-current")).toBe("page");
    expect(within(sidebar).getByRole("link", { name: /Picks/ }).textContent).toContain("9");
    const card = screen.getByRole("link", { name: /Track record/ });
    expect(card.getAttribute("href")).toBe("/performance");
    expect(card.textContent).toContain("Model · 2026 live");
    expect(card.textContent).toContain("32-24-1");
    expect(card.textContent).toContain("57.1%");
    expect(card.textContent).toContain("+4.6u");
    expect(card.textContent).toContain("CLV +0.9");
  });

  it("says the server can't be reached in the error state", () => {
    renderShell(null, "error");
    expect(screen.getAllByText("Can't reach the server").length).toBeGreaterThan(0);
    expect(screen.getByText("Unavailable until the server answers")).toBeTruthy();
    expect(screen.queryByText(/Updated /)).toBeNull();
  });
});

describe("week selector (TASK-061)", () => {
  const W = (week: number) => ({ season: 2026, season_type: "regular" as const, week });
  const nav = { shown: W(5), coming: W(6), weeks: [1, 2, 3, 4, 5, 6].map(W) };

  function renderThisWeek(weekNav?: typeof nav) {
    return render(
      <AppShell active="this-week" path="/" shell={SHELL} state="ready" weekNav={weekNav}>
        <main>content</main>
      </AppShell>,
    );
  }

  it("names the shown week, steps with arrows and sends the coming week to /", () => {
    renderThisWeek(nav);
    const bar = screen.getByRole("banner");
    expect(within(bar).getAllByText(/2026 · Week 5/).length).toBeGreaterThan(0);
    expect(within(bar).queryByText(/2026 · Week 6/)).toBeNull();
    expect(within(bar).getByRole("link", { name: "Previous week" }).getAttribute("href")).toBe(
      "/?season=2026&week=4",
    );
    expect(within(bar).getByRole("link", { name: "Next week" }).getAttribute("href")).toBe("/");
  });

  it("disables the arrow at the end of the list", () => {
    renderThisWeek({ ...nav, shown: W(1) });
    expect(screen.getByRole("link", { name: "Previous week" }).getAttribute("aria-disabled")).toBe("true");
    expect(screen.getByRole("link", { name: "Previous week" }).getAttribute("href")).toBeNull();
  });

  it("keeps the static label on a screen that passes no weekNav", () => {
    renderThisWeek();
    expect(screen.queryByRole("link", { name: "Previous week" })).toBeNull();
    expect(screen.queryByRole("button", { name: /2026 · Week/ })).toBeNull();
    expect(screen.getAllByText("2026 · Week 6").length).toBeGreaterThan(0);
  });
});
