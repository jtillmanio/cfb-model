// @vitest-environment jsdom
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { type Column, DataTable, type Row } from "./data-table";

afterEach(cleanup);

const TEAMS = [
  { id: 1, team: "Ohio State", rating: 27.4 },
  { id: 2, team: "Texas", rating: 25.9 },
  { id: 3, team: "Oregon", rating: 28.1 },
];

// Cells arrive rendered and sort values as plain data, so a server page can pass them (D-154).
const ROWS: Row[] = TEAMS.map((t) => ({
  key: t.id,
  cells: { team: t.team, rating: <span>{t.rating.toFixed(1)}</span> },
  sortValues: { rating: t.rating },
}));

const COLUMNS: Column[] = [
  { key: "team", header: "Team" },
  { key: "rating", header: "Rating", align: "right", sortable: true },
];

function table(density?: "comfortable" | "compact") {
  render(<DataTable caption="Ratings" columns={COLUMNS} rows={ROWS} density={density} />);
  return screen.getByRole("table", { name: "Ratings" });
}

/** The Team cell of each body row, top to bottom. */
const order = (t: HTMLElement) =>
  within(t)
    .getAllByRole("row")
    .slice(1)
    .map((r) => within(r).getAllByRole("cell")[0].textContent);

describe("DataTable density (AC-4, design/README.md › Table density)", () => {
  it("is comfortable by default: header 40px (h-10), rows 48px (h-12)", () => {
    const t = table();
    for (const th of within(t).getAllByRole("columnheader")) expect(th.className).toContain("h-10");
    for (const row of within(t).getAllByRole("row").slice(1)) expect(row.className).toContain("h-12");
  });

  it("is compact when asked: header 32px (h-8), rows 36px (h-9)", () => {
    const t = table("compact");
    for (const th of within(t).getAllByRole("columnheader")) {
      expect(th.className).toContain("h-8");
      expect(th.className).not.toContain("h-10");
    }
    for (const row of within(t).getAllByRole("row").slice(1)) {
      expect(row.className).toContain("h-9");
      expect(row.className).not.toContain("h-12");
    }
  });

  it("has a sticky header under the 56px app bar (top-14)", () => {
    const thead = table().querySelector("thead")!;
    expect(thead.className).toContain("sticky");
    expect(thead.className).toContain("top-14");
  });

  it("highlights a row on hover with the accent token", () => {
    const row = within(table()).getAllByRole("row")[1];
    expect(row.className).toContain("hover:bg-accent");
  });
});

describe("DataTable sorting (AC-4)", () => {
  it("a sortable header is a button inside a header with aria-sort; plain headers have neither", () => {
    const t = table();
    const team = within(t).getByRole("columnheader", { name: "Team" });
    expect(within(team).queryByRole("button")).toBeNull();
    expect(team.hasAttribute("aria-sort")).toBe(false);

    const rating = within(t).getByRole("columnheader", { name: /Rating/ });
    expect(within(rating).getByRole("button", { name: /Rating/ })).toBeTruthy();
    expect(rating.getAttribute("aria-sort")).toBe("none");
  });

  it("toggles aria-sort and the row order on click", async () => {
    const user = userEvent.setup();
    const t = table();
    const header = within(t).getByRole("columnheader", { name: /Rating/ });
    const button = within(header).getByRole("button");
    expect(order(t)).toEqual(["Ohio State", "Texas", "Oregon"]);

    await user.click(button);
    expect(header.getAttribute("aria-sort")).toBe("ascending");
    expect(order(t)).toEqual(["Texas", "Ohio State", "Oregon"]);

    await user.click(button);
    expect(header.getAttribute("aria-sort")).toBe("descending");
    expect(order(t)).toEqual(["Oregon", "Ohio State", "Texas"]);

    await user.click(button);
    expect(header.getAttribute("aria-sort")).toBe("ascending");
  });

  it("toggles on Enter and on Space from the keyboard", async () => {
    const user = userEvent.setup();
    const t = table();
    const header = within(t).getByRole("columnheader", { name: /Rating/ });

    await user.tab();
    expect(document.activeElement).toBe(within(header).getByRole("button"));
    await user.keyboard("{Enter}");
    expect(header.getAttribute("aria-sort")).toBe("ascending");
    await user.keyboard(" ");
    expect(header.getAttribute("aria-sort")).toBe("descending");
    expect(order(t)).toEqual(["Oregon", "Ohio State", "Texas"]);
  });

  it("marks the sorted column with the 2px ink rule", async () => {
    const user = userEvent.setup();
    const t = table();
    const header = within(t).getByRole("columnheader", { name: /Rating/ });
    expect(header.querySelector("[data-slot=sort-rule]")).toBeNull();
    await user.click(within(header).getByRole("button"));
    const rule = header.querySelector("[data-slot=sort-rule]")!;
    expect(rule.className).toContain("h-0.5");
    expect(rule.className).toContain("bg-foreground");
  });

  it("starts from a default sort when given one", () => {
    render(
      <DataTable
        caption="Ratings"
        columns={COLUMNS}
        rows={ROWS}
        defaultSort={{ key: "rating", direction: "descending" }}
      />,
    );
    const t = screen.getByRole("table", { name: "Ratings" });
    expect(order(t)).toEqual(["Oregon", "Ohio State", "Texas"]);
    expect(within(t).getByRole("columnheader", { name: /Rating/ }).getAttribute("aria-sort")).toBe("descending");
  });
});

describe("DataTable rows", () => {
  it("sorts rows with no value for the column last, either way", async () => {
    const user = userEvent.setup();
    const rows: Row[] = [
      { key: "a", cells: { team: "Bye week" }, sortValues: { rating: null } },
      ...ROWS,
      { key: "b", cells: { team: "New team" } },
    ];
    render(<DataTable caption="Ratings" columns={COLUMNS} rows={rows} />);
    const t = screen.getByRole("table", { name: "Ratings" });
    const button = within(t).getByRole("button", { name: /Rating/ });
    await user.click(button);
    expect(order(t)).toEqual(["Texas", "Ohio State", "Oregon", "Bye week", "New team"]);
    await user.click(button);
    expect(order(t)).toEqual(["Oregon", "Ohio State", "Texas", "Bye week", "New team"]);
  });

  it("renders an empty cell for a column the row has no cell for", () => {
    render(<DataTable caption="Ratings" columns={COLUMNS} rows={[{ key: 1, cells: { team: "Texas" } }]} />);
    const cells = within(screen.getAllByRole("row")[1]).getAllByRole("cell");
    expect(cells).toHaveLength(2);
    expect(cells[1].textContent).toBe("");
  });
});
