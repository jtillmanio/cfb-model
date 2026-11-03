// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { cn } from "@/lib/utils";

import { EdgePill } from "./edge-pill";
import { FilterChips } from "./filter-chips";
import { ResultMarker } from "./result-marker";
import { TierBadge } from "./tier-badge";

afterEach(cleanup);

describe("cn", () => {
  it("keeps text-caption beside text-muted-foreground", () => {
    // tailwind-merge alone reads both as colours and drops the first.
    expect(cn("text-caption", "text-muted-foreground")).toBe("text-caption text-muted-foreground");
    expect(cn("text-caption", "text-body")).toBe("text-body");
  });
});

describe("EdgePill (AC-1)", () => {
  it("edge 3.7 OSU at threshold 2.5 is filled +3.7 OSU (bg-edge)", () => {
    render(<EdgePill edgePts={3.7} home="OSU" away="UTAH" threshold={2.5} />);
    const pill = screen.getByText("+3.7 OSU");
    expect(pill.className).toContain("bg-edge");
    expect(pill.className).toContain("text-edge-foreground");
  });

  it("0.6 UTAH is plain muted text with no fill", () => {
    render(<EdgePill edgePts={-0.6} home="OSU" away="UTAH" threshold={2.5} />);
    const pill = screen.getByText("+0.6 UTAH");
    expect(pill.className).toContain("text-muted-foreground");
    expect(pill.className).not.toContain("bg-edge");
    expect(pill.className).not.toMatch(/\bbg-/);
  });

  it("exactly the threshold is filled", () => {
    render(<EdgePill edgePts={2.5} home="OSU" away="UTAH" threshold={2.5} />);
    expect(screen.getByText("+2.5 OSU").className).toContain("bg-edge");
  });

  it("a negative edge at the threshold is filled for the away side", () => {
    render(<EdgePill edgePts={-2.5} home="OSU" away="UTAH" threshold={2.5} />);
    expect(screen.getByText("+2.5 UTAH").className).toContain("bg-edge");
  });

  it("no line renders —", () => {
    render(<EdgePill edgePts={null} home="OSU" away="UTAH" threshold={2.5} />);
    const dash = screen.getByText("—");
    expect(dash.className).toContain("text-muted-foreground");
    expect(dash.className).not.toMatch(/\bbg-/);
  });

  it("locked shows the muted lock tone and loading shows a bar without text", () => {
    const { unmount } = render(
      <EdgePill edgePts={0.9} home="UNLV" away="BSU" threshold={2.5} locked />,
    );
    const locked = screen.getByText("+0.9 UNLV");
    expect(locked.className).toContain("text-locked");
    expect(locked.className).toContain("bg-muted");
    unmount();

    const { container } = render(
      <EdgePill edgePts={3.7} home="OSU" away="UTAH" threshold={2.5} loading />,
    );
    expect(container.textContent).toBe("");
    expect(container.firstElementChild?.className).toContain("bg-secondary");
  });
});

describe("TierBadge (AC-2)", () => {
  it("tiers A, B and C use three distinct tier tokens, C outlined", () => {
    const { unmount } = render(<TierBadge tier="A" />);
    const a = screen.getByText("A");
    expect(a.className).toContain("bg-tier-a");
    expect(a.className).toContain("text-tier-a-foreground");
    unmount();

    const { unmount: unmountB } = render(<TierBadge tier="B" />);
    const b = screen.getByText("B");
    expect(b.className).toContain("bg-tier-b");
    expect(b.className).toContain("text-tier-b-foreground");
    expect(b.className).not.toContain("ring-1");
    unmountB();

    render(<TierBadge tier="C" />);
    const c = screen.getByText("C");
    expect(c.className).toContain("bg-tier-c");
    expect(c.className).toContain("text-tier-c-foreground");
    expect(c.className).toContain("ring-1");
  });

  it("no pick renders — and the label adds Tier A", () => {
    const { unmount } = render(<TierBadge tier={null} />);
    expect(screen.getByText("—")).toBeTruthy();
    unmount();

    render(<TierBadge tier="A" label />);
    expect(screen.getByText("Tier A")).toBeTruthy();
    expect(screen.getByText("A")).toBeTruthy();
  });

  it("loading draws a bar with no letter", () => {
    const { container } = render(<TierBadge tier="A" loading />);
    expect(container.textContent).toBe("");
    expect(container.firstElementChild?.className).toContain("bg-secondary");
  });
});

describe("ResultMarker (AC-2)", () => {
  const cases = [
    ["covered", "✓", "Covered", "text-pos"],
    ["not_covered", "✗", "Not covered", "text-neg"],
    ["push", "P", "Push", "text-push"],
  ] as const;

  for (const [result, glyph, label, tone] of cases) {
    it(`${result} puts the glyph ${glyph} first with a screen-reader label`, () => {
      const { container } = render(<ResultMarker result={result} />);
      const root = container.firstElementChild as HTMLElement;
      expect(root.className).toContain(tone);
      // Glyph first in document order, hidden from assistive tech; the label follows.
      const [first, second] = Array.from(root.children) as HTMLElement[];
      expect(first.textContent).toBe(glyph);
      expect(first.getAttribute("aria-hidden")).toBe("true");
      expect(second.textContent).toBe(label);
      expect(second.className).toContain("sr-only");
    });
  }

  it("pending is a dashed square with a screen-reader label", () => {
    const { container } = render(<ResultMarker result="pending" />);
    const root = container.firstElementChild as HTMLElement;
    expect(root.className).toContain("border-dashed");
    expect(root.className).toContain("border-input");
    expect(screen.getByText("Pending").className).toContain("sr-only");
  });

  it("the labelled variant shows the label instead of hiding it", () => {
    render(<ResultMarker result="covered" showLabel />);
    expect(screen.getByText("Covered").className).not.toContain("sr-only");
  });
});

describe("FilterChips (AC-3)", () => {
  const options = [
    { value: "all", label: "All" },
    { value: "picks", label: "Picks only" },
    { value: "ranked", label: "Ranked" },
  ];

  it("chips are buttons with aria-pressed matching selected (ink fill + check)", () => {
    const { container } = render(<FilterChips options={options} defaultSelected={["picks"]} />);
    const buttons = screen.getAllByRole("button");
    expect(buttons).toHaveLength(3);
    for (const button of buttons) expect(button.tagName).toBe("BUTTON");

    const picks = screen.getByRole("button", { name: "Picks only" });
    expect(picks.getAttribute("aria-pressed")).toBe("true");
    // The ink fill is a data-state variant (jsdom computes no CSS), so check the state hook and
    // the variant that paints it.
    expect(picks.getAttribute("data-state")).toBe("on");
    expect(picks.className).toContain("data-[state=on]:bg-primary");
    expect(picks.className).toContain("data-[state=on]:text-primary-foreground");
    expect(picks.querySelector("svg")).not.toBeNull();

    const all = screen.getByRole("button", { name: "All" });
    expect(all.getAttribute("aria-pressed")).toBe("false");
    expect(all.getAttribute("data-state")).toBe("off");
    expect(all.querySelector("svg")).toBeNull();
    expect(container.querySelectorAll("svg")).toHaveLength(1);
  });

  it("click toggles and reports the selection", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<FilterChips options={options} onChange={onChange} />);

    const ranked = screen.getByRole("button", { name: "Ranked" });
    expect(ranked.getAttribute("aria-pressed")).toBe("false");
    await user.click(ranked);
    expect(ranked.getAttribute("aria-pressed")).toBe("true");
    expect(onChange).toHaveBeenLastCalledWith(["ranked"]);
    await user.click(ranked);
    expect(ranked.getAttribute("aria-pressed")).toBe("false");
    expect(onChange).toHaveBeenLastCalledWith([]);
  });

  it("Enter and Space toggle", async () => {
    const user = userEvent.setup();
    render(<FilterChips options={options} />);

    const all = screen.getByRole("button", { name: "All" });
    await user.tab();
    expect(document.activeElement).toBe(all);
    await user.keyboard("{Enter}");
    expect(all.getAttribute("aria-pressed")).toBe("true");
    await user.keyboard(" ");
    expect(all.getAttribute("aria-pressed")).toBe("false");
  });

  it("controlled: selection comes from the prop, not from clicks", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<FilterChips options={options} selected={["all"]} onChange={onChange} />);

    await user.click(screen.getByRole("button", { name: "Ranked" }));
    expect(onChange).toHaveBeenCalledWith(["all", "ranked"]);
    expect(screen.getByRole("button", { name: "Ranked" }).getAttribute("aria-pressed")).toBe(
      "false",
    );
  });
});
