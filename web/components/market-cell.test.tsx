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

describe("MarketCell stacked (This Week at 768 and on phones, This Week Tablet / Mobile boards)", () => {
  it("puts the current line over \"opened −28\", muted, with a sparkline that tablets hide", () => {
    const { container } = render(
      <MarketCell stacked opener={-28} snapshots={[-28, -27.5]} current={-27.5} home="OSU" away="PUR" />,
    );
    const current = screen.getByText("OSU −27.5");
    const opened = screen.getByText("opened −28");
    expect(current.compareDocumentPosition(opened) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(opened.closest("[data-slot=line-history]")!.className).toContain("text-muted-foreground");
    expect(current.className).not.toContain("text-muted-foreground");
    expect(points(container)).toHaveLength(2);
    expect(container.querySelector("svg")!.getAttribute("class")).toContain("md:hidden");
  });

  it("reads \"no move\" when the line never moved", () => {
    render(<MarketCell stacked opener={-9} snapshots={[-9, -9]} current={-9} home="MICH" away="NW" />);
    expect(screen.getByText("no move")).toBeTruthy();
    expect(screen.queryByText(/opened/)).toBeNull();
  });

  it("reads the opener from the current favorite's side", () => {
    render(<MarketCell stacked opener={-1} snapshots={[]} current={1.5} home="TEX" away="OU" />);
    expect(screen.getByText("opened +1")).toBeTruthy();
    expect(screen.getByText("OU −1.5")).toBeTruthy();
  });

  it("shows no opener line when none was recorded, and No line without a current line", () => {
    const { container } = render(
      <MarketCell stacked opener={null} snapshots={[]} current={-3} home="CLEM" away="FUR" />,
    );
    expect(screen.getByText("CLEM −3")).toBeTruthy();
    expect(container.querySelector("[data-slot=line-history]")).toBeNull();
    cleanup();
    render(<MarketCell stacked opener={null} snapshots={[]} current={null} home="CLEM" away="FUR" />);
    expect(screen.getByText("No line")).toBeTruthy();
  });
});

describe("MarketCell past (a past season, Market Extras.dc.html › Past season, TASK-061)", () => {
  it("draws the opener, two dots joined by a dashed line, then the close, titled \"Past season\"", () => {
    const { container } = render(<MarketCell past opener={-3.5} snapshots={[]} current={-2.5} home="TEX" away="OU" />);
    const opener = screen.getByText("−3.5");
    const close = screen.getByText("TEX −2.5");
    const svg = container.querySelector("svg")!;
    const history = opener.closest("[data-slot=line-history]")!;

    expect(history.getAttribute("title")).toBe("Past season: opening and closing line only");
    expect(history.className).toContain("text-muted-foreground");
    expect(opener.compareDocumentPosition(svg) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(svg.compareDocumentPosition(close) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    // Two dots, no trend line, one dashed join.
    expect(container.querySelectorAll("circle")).toHaveLength(2);
    expect(container.querySelector("polyline")).toBeNull();
    expect(container.querySelector("line")!.getAttribute("class")).toContain("[stroke-dasharray");
    // The open is hollow, the close filled.
    const [open, closing] = [...container.querySelectorAll("circle")];
    expect(open.getAttribute("class")).toContain("fill-muted");
    expect(closing.getAttribute("class")).toContain("fill-muted-foreground");
  });

  it("ignores the snapshots: a full history still draws only the open and the close", () => {
    const { container } = render(
      <MarketCell past opener={-3.5} snapshots={[-3.5, -3, -2.5]} current={-2.5} home="TEX" away="OU" />,
    );
    expect(container.querySelectorAll("circle")).toHaveLength(2);
    expect(container.querySelector("polyline")).toBeNull();
  });

  it("puts the dots at mid-height when the line never moved, and apart when it did", () => {
    const y = (container: HTMLElement) =>
      [...container.querySelectorAll("circle")].map((c) => Number(c.getAttribute("cy")));
    const flat = render(<MarketCell past opener={-9} snapshots={[]} current={-9} home="MICH" away="NW" />);
    expect(new Set(y(flat.container)).size).toBe(1);
    cleanup();
    const moved = render(<MarketCell past opener={-3.5} snapshots={[]} current={-2.5} home="TEX" away="OU" />);
    const [a, b] = y(moved.container);
    expect(a).toBeLessThan(b); // the more favoured line is at the top
  });

  it("with no opener shows the close alone, and No line with no close", () => {
    const { container } = render(<MarketCell past opener={null} snapshots={[]} current={-3} home="CLEM" away="FUR" />);
    expect(screen.getByText("CLEM −3")).toBeTruthy();
    expect(container.querySelector("svg")).toBeNull();
    cleanup();
    render(<MarketCell past opener={-3} snapshots={[]} current={null} home="CLEM" away="FUR" />);
    expect(screen.getByText("No line")).toBeTruthy();
  });

  it("stacked: the close over the dots and \"opened −3.5\"; \"no move\" when it never moved", () => {
    const { container } = render(
      <MarketCell past stacked opener={-3.5} snapshots={[]} current={-2.5} home="TEX" away="OU" />,
    );
    const close = screen.getByText("TEX −2.5");
    const opened = screen.getByText("opened −3.5");
    expect(close.compareDocumentPosition(opened) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(opened.closest("[data-slot=line-history]")!.getAttribute("title")).toBe(
      "Past season: opening and closing line only",
    );
    expect(container.querySelectorAll("circle")).toHaveLength(2);
    cleanup();
    render(<MarketCell past stacked opener={-9} snapshots={[]} current={-9} home="MICH" away="NW" />);
    expect(screen.getByText("no move")).toBeTruthy();
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
