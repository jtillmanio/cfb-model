// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { hasRemoteMatch } from "next/dist/shared/lib/match-remote-pattern";
import { afterEach, describe, expect, it } from "vitest";

import nextConfig from "../next.config";

import { TeamChip } from "./team-chip";

afterEach(cleanup);

// CFBD's `logos[0]` for Ohio State, as staging stores it in `teams.logo_url` (D-146).
const OSU_LOGO = "https://cdn.collegefootballdata.com/logos/500/194.png";

describe("TeamChip logo slot (AC-1, D-075, D-146)", () => {
  it("renders a same-origin logo at most 20px", () => {
    const { container } = render(<TeamChip abbreviation="OSU" logoUrl={OSU_LOGO} color="#BB0000" />);
    const img = container.querySelector("img");
    expect(img).not.toBeNull();
    // The browser asks the app's own image optimizer, never CFBD's CDN (D-101).
    const src = img!.getAttribute("src")!;
    expect(src.startsWith("/_next/image?")).toBe(true);
    for (const candidate of (img!.getAttribute("srcset") ?? "").split(",")) {
      expect(candidate.trim().startsWith("/_next/image?")).toBe(true);
    }
    expect(new URL(src, "http://app.test").host).toBe("app.test");
    expect(Number(img!.getAttribute("width"))).toBeLessThanOrEqual(20);
    expect(Number(img!.getAttribute("height"))).toBeLessThanOrEqual(20);
    // Decorative: the name beside it says which team it is.
    expect(img!.getAttribute("alt")).toBe("");
  });

  it("is a logo URL the image optimizer will fetch (next.config remotePatterns)", () => {
    const patterns = nextConfig.images?.remotePatterns ?? [];
    expect(hasRemoteMatch([], patterns, new URL(OSU_LOGO))).toBe(true);
    expect(hasRemoteMatch([], patterns, new URL("https://a.espncdn.com/i/teamlogos/ncaa/500/194.png"))).toBe(false);
  });

  it("renders a 20px colour dot and no image without a logo", () => {
    const { container } = render(<TeamChip abbreviation="OSU" logoUrl={null} color="#BB0000" />);
    expect(container.querySelector("img")).toBeNull();
    const dot = container.querySelector<HTMLElement>("[data-slot=team-dot]");
    expect(dot).not.toBeNull();
    expect(dot!.style.backgroundColor).toBe("rgb(187, 0, 0)");
    expect(dot!.className).toContain("size-5");
    expect(dot!.className).toContain("rounded-full");
  });

  it("puts the team colour only on an element with no text", () => {
    const { container } = render(
      <TeamChip abbreviation="OSU" logoUrl={null} color="#BB0000" rank={1} neutral fcs />,
    );
    const coloured = [...container.querySelectorAll<HTMLElement>("*")].filter(
      (el) => el.style.backgroundColor || el.style.color || el.style.background,
    );
    expect(coloured).toHaveLength(1);
    expect(coloured[0].textContent).toBe("");
    expect(coloured[0].children).toHaveLength(0);
  });

  it("falls back to a muted dot when the team has no colour either", () => {
    const { container } = render(<TeamChip abbreviation="FUR" logoUrl={null} color={null} />);
    const dot = container.querySelector<HTMLElement>("[data-slot=team-dot]")!;
    expect(dot.style.backgroundColor).toBe("");
    expect(dot.className).toContain("bg-muted");
  });

  it("drops the team colour when locked: a muted dot, a greyed logo, locked text", () => {
    const { container, rerender } = render(
      <TeamChip abbreviation="UNLV" logoUrl={null} color="#CF0A2C" locked />,
    );
    const dot = container.querySelector<HTMLElement>("[data-slot=team-dot]")!;
    expect(dot.style.backgroundColor).toBe("");
    expect(dot.className).toContain("bg-muted");
    expect(screen.getByText("UNLV").closest("[data-slot=team-chip]")!.className).toContain("text-locked");

    rerender(<TeamChip abbreviation="UNLV" logoUrl={OSU_LOGO} color="#CF0A2C" locked />);
    expect(container.querySelector("img")!.className).toContain("grayscale");
  });
});

describe("TeamChip rank, FCS and neutral (AC-2)", () => {
  it("shows the rank small and muted before the name, with no #", () => {
    render(<TeamChip abbreviation="OSU" logoUrl={null} color="#BB0000" rank={1} />);
    const rank = screen.getByText("1");
    const name = screen.getByText("OSU");
    expect(rank.className).toContain("text-caption");
    expect(rank.className).toContain("text-muted-foreground");
    expect(rank.compareDocumentPosition(name) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByText("OSU").closest("[data-slot=team-chip]")!.textContent).not.toContain("#");
  });

  it("shows no rank when unranked", () => {
    const { container } = render(<TeamChip abbreviation="PUR" logoUrl={null} color="#CEB888" />);
    expect(container.textContent).toBe("PUR");
  });

  it("shows the full name when asked", () => {
    render(<TeamChip abbreviation="OSU" school="Ohio State" full logoUrl={null} color="#BB0000" />);
    expect(screen.getByText("Ohio State")).toBeTruthy();
    expect(screen.queryByText("OSU")).toBeNull();
  });

  it("shows an FCS tag and an N marker from props, and neither without them", () => {
    const { rerender, container } = render(
      <TeamChip abbreviation="FUR" logoUrl={null} color="#582C83" fcs neutral />,
    );
    expect(screen.getByText("FCS").className).toContain("text-muted-foreground");
    expect(screen.getByText("N")).toBeTruthy();
    expect(screen.getByTitle("Neutral site")).toBeTruthy();
    rerender(<TeamChip abbreviation="FUR" logoUrl={null} color="#582C83" />);
    expect(container.textContent).toBe("FUR");
  });
});
