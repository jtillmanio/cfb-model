// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { MarketCell } from "./market-cell";
import { Sparkline } from "./sparkline";

afterEach(cleanup);

/** The polyline's points as [x, y] pairs. */
function points(container: HTMLElement): [number, number][] {
  const line = container.querySelector("polyline");
  if (!line) return [];
  return line
    .getAttribute("points")!
    .trim()
    .split(/\s+/)
    .map((p) => p.split(",").map(Number) as [number, number]);
}

describe("MarketCell (AC-3, design/README.md › LineMovementCell)", () => {
  it("opener −28, a sparkline with one point per snapshot, then OSU −27.5; opener and sparkline muted", () => {
    const { container } = render(
      <MarketCell opener={-28} snapshots={[-28, -27.5]} current={-27.5} home="OSU" away="UTAH" />,
    );
    const opener = screen.getByText("−28");
    const current = screen.getByText("OSU −27.5");
    const sparkline = container.querySelector("svg")!;

    // Read left to right: opener, sparkline, current line.
    expect(opener.compareDocumentPosition(sparkline) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(sparkline.compareDocumentPosition(current) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

    expect(points(container)).toHaveLength(2);
    // The opener and its sparkline sit in the muted token; the current line is ink.
    const history = opener.closest("[data-slot=line-history]")!;
    expect(history.className).toContain("text-muted-foreground");
    expect(history.contains(sparkline)).toBe(true);
    expect(container.querySelector("polyline")!.getAttribute("class")).toContain("stroke-muted-foreground");
    expect(current.className).not.toContain("text-muted-foreground");
  });

  it("draws the line moving down as the favorite's number shrinks", () => {
    const { container } = render(
      <MarketCell opener={-28} snapshots={[-28, -28, -27.5, -27.5]} current={-27.5} home="OSU" away="UTAH" />,
    );
    const ys = points(container).map(([, y]) => y);
    expect(ys).toHaveLength(4);
    expect(ys[0]).toBeLessThan(ys[3]);
  });

  it("draws a flat sparkline when the line is unchanged", () => {
    const { container } = render(<MarketCell opener={-9} snapshots={[]} current={-9} home="MICH" away="MINN" />);
    expect(screen.getByText("−9")).toBeTruthy();
    expect(screen.getByText("MICH −9")).toBeTruthy();
    const ys = points(container).map(([, y]) => y);
    expect(ys.length).toBeGreaterThanOrEqual(2);
    expect(new Set(ys).size).toBe(1);
  });

  it("with no in-between snapshots, joins the opener to the current line", () => {
    const { container } = render(<MarketCell opener={-3} snapshots={[]} current={-2.5} home="TEX" away="OU" />);
    expect(points(container)).toHaveLength(2);
  });

  it("renders No line, with no opener and no sparkline, when there is no line", () => {
    const { container } = render(<MarketCell opener={null} snapshots={[]} current={null} home="OSU" away="FUR" />);
    const noLine = screen.getByText("No line");
    expect(noLine.className).toContain("text-muted-foreground");
    expect(container.querySelector("svg")).toBeNull();
    expect(container.textContent).toBe("No line");
  });

  it("shows the opener from the current favorite's side when the favorite flipped", () => {
    render(<MarketCell opener={-1} snapshots={[-1, 1.5]} current={1.5} home="TEX" away="OU" />);
    expect(screen.getByText("+1")).toBeTruthy();
    expect(screen.getByText("OU −1.5")).toBeTruthy();
  });
});

describe("Sparkline", () => {
  it("spans the box, one point per value, top = most favored", () => {
    const { container } = render(<Sparkline values={[-22.5, -22, -21.5, -21]} />);
    const pts = points(container);
    expect(pts.map(([x]) => x)).toEqual([0, 22 / 3, 44 / 3, 22].map((x) => Number(x.toFixed(1))));
    expect(pts[0][1]).toBe(1);
    expect(pts[3][1]).toBe(9);
  });

  it("is hidden from assistive tech: the numbers beside it carry the meaning", () => {
    const { container } = render(<Sparkline values={[-9, -9]} />);
    expect(container.querySelector("svg")!.getAttribute("aria-hidden")).toBe("true");
    expect(points(container).map(([, y]) => y)).toEqual([5, 5]);
  });
});
