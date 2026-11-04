"use client";

import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import { type ReactNode, useState } from "react";

import { cn } from "@/lib/utils";

// DataTable (design/README.md › Components › Tables & lists and › Table density;
// Components.dc.html › Data table). Comfortable is the default (header 40, rows 48); compact
// (header 32, rows 36) is for This Week's desktop slate, Rankings and the Lab (D-084). The header
// sticks under the 56px app bar. A sortable header is a <button> inside a <th aria-sort>: ARIA
// allows aria-sort only on the column header. The sorted column gets the 2px ink rule and an
// arrow; an unsorted sortable one shows a sort hint on hover. Collapsing to cards below 768 is each
// screen's own job.
//
// Columns and rows are plain data: a row carries its cells already rendered and its sort values,
// so a server component can pass them straight in (a function can't cross to a client component).

export type SortDirection = "ascending" | "descending";
export type SortState = { key: string; direction: SortDirection };
export type SortValue = number | string | null;

export type Column = {
  key: string;
  header: string;
  /** Numbers are right-aligned. */
  align?: "left" | "right";
  /** Sorts by each row's `sortValues[key]`. A row with no value sorts last either way. */
  sortable?: boolean;
};

export type Row = {
  key: string | number;
  /** Rendered cells by column key; a missing one is an empty cell. */
  cells: Record<string, ReactNode>;
  sortValues?: Record<string, SortValue>;
};

type DataTableProps = {
  /** Names the table for assistive tech; not shown. */
  caption: string;
  columns: Column[];
  rows: Row[];
  density?: "comfortable" | "compact";
  defaultSort?: SortState | null;
  className?: string;
};

const DENSITY = {
  comfortable: { header: "h-10", row: "h-12" },
  compact: { header: "h-8", row: "h-9" },
} as const;

export function sortRows(rows: Row[], sort: SortState | null): Row[] {
  if (!sort) return rows;
  const sign = sort.direction === "ascending" ? 1 : -1;
  const value = (row: Row) => row.sortValues?.[sort.key] ?? null;
  // Array.prototype.sort is stable, so equal values keep their order.
  return [...rows].sort((x, y) => {
    const a = value(x);
    const b = value(y);
    if (a === b) return 0;
    if (a === null) return 1;
    if (b === null) return -1;
    return sign * (a < b ? -1 : 1);
  });
}

export function DataTable({
  caption,
  columns,
  rows,
  density = "comfortable",
  defaultSort = null,
  className,
}: DataTableProps) {
  const [sort, setSort] = useState<SortState | null>(defaultSort);
  const heights = DENSITY[density];

  const toggle = (key: string) =>
    setSort((current) => ({
      key,
      direction: current?.key === key && current.direction === "ascending" ? "descending" : "ascending",
    }));

  return (
    <table className={cn("w-full border-separate border-spacing-0 text-body", className)}>
      <caption className="sr-only">{caption}</caption>
      <thead className="sticky top-14 z-10 bg-card">
        <tr>
          {columns.map((column) => {
            const sorted = sort?.key === column.key ? sort.direction : null;
            const right = column.align === "right";
            return (
              <th
                key={column.key}
                scope="col"
                aria-sort={column.sortable ? (sorted ?? "none") : undefined}
                className={cn(
                  heights.header,
                  "relative border-b px-3 text-caption font-medium whitespace-nowrap text-muted-foreground",
                  right ? "text-right" : "text-left",
                  sorted && "text-foreground",
                )}
              >
                {column.sortable ? (
                  <button
                    type="button"
                    onClick={() => toggle(column.key)}
                    className="group -mx-1.5 inline-flex h-7 items-center gap-1.5 rounded-md px-1.5 hover:bg-accent hover:text-foreground focus-visible:-outline-offset-2"
                  >
                    <span>{column.header}</span>
                    {sorted === "ascending" ? (
                      <ArrowUp aria-hidden className="size-3" />
                    ) : sorted === "descending" ? (
                      <ArrowDown aria-hidden className="size-3" />
                    ) : (
                      <ArrowUpDown aria-hidden className="size-3 opacity-0 group-hover:opacity-100 group-focus-visible:opacity-100" />
                    )}
                  </button>
                ) : (
                  column.header
                )}
                {sorted && (
                  <span data-slot="sort-rule" aria-hidden className="absolute inset-x-0 bottom-0 h-0.5 bg-foreground" />
                )}
              </th>
            );
          })}
        </tr>
      </thead>
      <tbody>
        {sortRows(rows, sort).map((row) => (
          <tr
            key={row.key}
            className={cn(
              heights.row,
              "hover:bg-accent has-[:focus-visible]:bg-accent has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring has-[:focus-visible]:ring-inset",
            )}
          >
            {columns.map((column) => (
              <td
                key={column.key}
                className={cn("border-b px-3 whitespace-nowrap", column.align === "right" && "text-right")}
              >
                {row.cells[column.key]}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
