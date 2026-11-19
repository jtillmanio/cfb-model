"use client";

import { Search } from "lucide-react";
import { useId, useState } from "react";

import { type ImportTeam, teamName } from "@/lib/contest";
import { cn } from "@/lib/utils";

// The inline team picker (Contest Desktop › parse, "Needs team"; Components › contest paste row,
// "autocomplete open with focus"). Its options are the API's candidates for the name: teams of the
// contest's sports playing that day, best first (D-172). A pick stays on the page until Confirm,
// which saves it as an alias; "Change" reopens it.

const LEAGUE: Record<string, string> = { cfb: "CFB", nfl: "NFL" };

export function TeamDot({ color, className }: { color: string | null; className?: string }) {
  return (
    <span
      aria-hidden
      className={cn("size-4 shrink-0 rounded-full bg-muted ring-1 ring-border", className)}
      // A team's colour is data, not a design token (the team chip draws its dot the same way).
      style={color ? { backgroundColor: color } : undefined}
    />
  );
}

function matches(team: ImportTeam, query: string): boolean {
  const words = query.toLowerCase().match(/[a-z0-9]+/g) ?? [];
  const hay = [team.school, team.mascot ?? "", team.abbreviation ?? ""].join(" ").toLowerCase().match(/[a-z0-9]+/g) ?? [];
  return words.every((w) => hay.some((h) => h.startsWith(w)));
}

export function TeamPicker({
  name,
  side,
  line,
  candidates,
  picked,
  onPick,
}: {
  /** The name as the page writes it, e.g. "Hou Texans". */
  name: string;
  side: "Away" | "Home";
  /** That side's line as pasted, e.g. "−1". */
  line: string;
  candidates: readonly ImportTeam[];
  picked: ImportTeam | null;
  onPick: (team: ImportTeam | null) => void;
}) {
  const [query, setQuery] = useState("");
  const listId = useId();
  const shown = query.trim() === "" ? candidates : candidates.filter((t) => matches(t, query));
  const label = `${side} · “${name}” · ${line}`;

  return (
    <div data-slot="team-picker" className="flex min-w-0 flex-col gap-1">
      <span className="text-caption font-semibold tracking-wider text-muted-foreground uppercase">{label}</span>
      {picked ? (
        <button
          type="button"
          onClick={() => onPick(null)}
          aria-label={`${teamName(picked)} for “${name}”. Change`}
          className="flex min-h-11 items-center gap-2 rounded-md border border-input bg-background px-2.5 text-left hover:bg-accent"
        >
          <TeamDot color={picked.color} />
          <span className="text-label font-medium">{teamName(picked)}</span>
          <span className="text-caption text-muted-foreground">{LEAGUE[picked.sport_id] ?? picked.sport_id}</span>
          <span className="flex-1" />
          <span className="text-caption text-muted-foreground">Change</span>
        </button>
      ) : (
        <div className="flex flex-col overflow-hidden rounded-md border border-ring bg-popover shadow-lg">
          <label className="flex min-h-11 items-center gap-2 border-b px-2.5">
            <Search aria-hidden className="size-3.5 shrink-0 text-muted-foreground" />
            <span className="sr-only">Find the team “{name}” means</span>
            <input
              type="search"
              value={query}
              placeholder={name}
              aria-controls={listId}
              autoComplete="off"
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && shown.length > 0) {
                  e.preventDefault();
                  onPick(shown[0]);
                }
              }}
              className="min-h-11 min-w-0 flex-1 bg-transparent text-label outline-none placeholder:text-muted-foreground"
            />
          </label>
          <ul id={listId} aria-label={`Teams “${name}” may mean`} className="flex flex-col">
            {shown.map((team, i) => (
              <li key={team.id}>
                <button
                  type="button"
                  onClick={() => onPick(team)}
                  className={cn(
                    "flex min-h-11 w-full items-center gap-2 px-2.5 text-left hover:bg-accent",
                    i === 0 && "bg-accent",
                  )}
                >
                  <TeamDot color={team.color} />
                  <span className="text-label font-medium">{teamName(team)}</span>
                  <span className="text-caption text-muted-foreground">{LEAGUE[team.sport_id] ?? team.sport_id}</span>
                  <span className="flex-1" />
                  {i === 0 ? <span className="text-caption text-muted-foreground">best match · ↵</span> : null}
                </button>
              </li>
            ))}
            {shown.length === 0 ? (
              <li className="flex min-h-11 items-center px-2.5 text-caption text-muted-foreground">
                {candidates.length === 0
                  ? "No team of this contest's sports plays that day with a name like this."
                  : "No team playing that day has that name."}
              </li>
            ) : null}
          </ul>
        </div>
      )}
    </div>
  );
}
