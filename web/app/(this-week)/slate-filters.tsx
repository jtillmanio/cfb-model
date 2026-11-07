"use client";

import { createContext, type ReactNode, useContext, useState } from "react";

import { FilterChips } from "@/components/filter-chips";
import { type RecordStrip, type SlateFilter, showingText } from "@/lib/slate";

import { RecordStripButton } from "./record-strip";

// The Picks only filter (F-32, TASK-057). The rows stay server-rendered: this island holds only
// the All / Picks only state, and CSS (globals.css, `[data-filter="picks"]`) hides the rows and
// windows with no pick. So 54 rows are never client props and the page keeps its one API call.

type Filter = { filter: SlateFilter; set: (filter: SlateFilter) => void };

const FilterContext = createContext<Filter | null>(null);

function useFilter(): Filter {
  const value = useContext(FilterContext);
  if (value === null) throw new Error("SlateFilterRoot is missing");
  return value;
}

/** Wraps everything the filter reaches: the strip, the chips, the rows and the footer. */
export function SlateFilterRoot({ children }: { children: ReactNode }) {
  const [filter, set] = useState<SlateFilter>("all");
  return (
    <FilterContext.Provider value={{ filter, set }}>
      <div data-filter={filter}>{children}</div>
    </FilterContext.Provider>
  );
}

/** The strip, as the button that toggles Picks only. */
export function SlateStrip({ strip }: { strip: RecordStrip }) {
  const { filter, set } = useFilter();
  return (
    <RecordStripButton
      strip={strip}
      pressed={filter === "picks"}
      onToggle={() => set(filter === "picks" ? "all" : "picks")}
    />
  );
}

/** All / Picks only. Clicking the pressed chip again returns to all. */
export function SlateChips() {
  const { filter, set } = useFilter();
  return (
    <FilterChips
      label="Filter games"
      selected={[filter]}
      onChange={(next) => {
        // A controlled group reports the toggled chip: none left means the pressed one was clicked.
        const clicked = next.find((value) => value !== filter);
        set(clicked === "picks" ? "picks" : "all");
      }}
      options={[
        { value: "all", label: "All" },
        {
          value: "picks",
          label: (
            <>
              Picks<span className="max-md:hidden"> only</span>
            </>
          ),
        },
      ]}
    />
  );
}

/** The footer's count: `Showing 54 of 54 games`, or `9 games with a pick · of 54`. */
export function ShowingCount({ shown, total, picks }: { shown: number; total: number; picks: number }) {
  const { filter } = useFilter();
  return <span data-slot="showing">{showingText(filter, { shown, games: total, picks })}</span>;
}
