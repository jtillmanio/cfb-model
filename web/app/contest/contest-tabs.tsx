"use client";

import { ChevronRight } from "lucide-react";
import { useState } from "react";

import { type ContestPage, seasonCards, standingText } from "@/lib/contest";
import { cn } from "@/lib/utils";

import { ContestPicks } from "./pick-tray";
import { ResultsStanding } from "./results-standing";
import { RulesPanel } from "./rules-panel";

// The confirmed week's three tabs (S-02, TASK-073): This week's picks (the ranked slate and the
// tray), Results & standing, and Rules (desktop only: read-only, the form is M8.8). The season
// chip at the right is the board's header chip and opens Results. Tab state is the browser's: a
// reload opens on the picks, as the board does.

type Tab = "picks" | "results" | "rules";

const TABS: { id: Tab; label: string; className?: string }[] = [
  { id: "picks", label: "This week's picks" },
  { id: "results", label: "Results & standing" },
  { id: "rules", label: "Rules", className: "max-lg:hidden" },
];

export function ContestTabs({ page, period }: { page: ContestPage; period: number }) {
  const [tab, setTab] = useState<Tab>("picks");
  const { contest, results, standing } = page;
  const picks = contest.rules.picks_per_period;
  const cards = results ? seasonCards(results, picks) : null;
  const place = standingText(standing);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <div role="tablist" aria-label="Contest" className="flex rounded-md border">
          {TABS.map(({ id, label, className }) => (
            <button
              key={id}
              type="button"
              role="tab"
              id={`contest-tab-${id}`}
              aria-selected={tab === id}
              aria-controls={`contest-panel-${id}`}
              onClick={() => setTab(id)}
              className={cn(
                "min-h-11 min-w-11 px-3 text-label font-medium first:rounded-l-md last:rounded-r-md",
                tab === id ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:bg-accent",
                className,
              )}
            >
              {label}
            </button>
          ))}
        </div>
        {cards ? (
          <button
            type="button"
            data-slot="season-chip"
            aria-label="Season record: open results and standing"
            onClick={() => setTab("results")}
            className="inline-flex min-h-11 items-center gap-3 rounded-md border px-3 text-label hover:bg-accent md:ml-auto"
          >
            <span className="text-muted-foreground">Season</span>
            <span>
              <strong className="font-semibold">{cards.you.record}</strong> <span className="text-muted-foreground">you</span>
            </span>
            {cards.model ? (
              <span>
                <strong className="font-semibold">{cards.model.record}</strong>{" "}
                <span className="text-muted-foreground">{cards.model.label.toLowerCase()}</span>
              </span>
            ) : null}
            {place ? (
              <span>
                <strong className="font-semibold">{place.place}</strong>
              </span>
            ) : null}
            <ChevronRight aria-hidden className="size-4 text-muted-foreground" />
          </button>
        ) : null}
      </div>

      <div role="tabpanel" id="contest-panel-picks" aria-labelledby="contest-tab-picks" hidden={tab !== "picks"}>
        <ContestPicks
          contestId={contest.id}
          contestName={contest.name}
          period={period}
          picks={picks}
          games={page.games}
          entries={page.entries}
        />
      </div>
      <div role="tabpanel" id="contest-panel-results" aria-labelledby="contest-tab-results" hidden={tab !== "results"}>
        <ResultsStanding
          contestId={contest.id}
          period={period}
          picks={picks}
          results={results}
          standing={standing}
          games={page.games}
          entries={page.entries}
        />
      </div>
      <div
        role="tabpanel"
        id="contest-panel-rules"
        aria-labelledby="contest-tab-rules"
        hidden={tab !== "rules"}
        className="max-lg:hidden"
      >
        <RulesPanel name={contest.name} rules={contest.rules} />
      </div>
    </div>
  );
}
