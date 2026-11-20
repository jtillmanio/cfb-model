"use client";

import { Check, Pencil } from "lucide-react";
import { useState, useTransition } from "react";

import {
  type ContestEntry,
  type ContestGame,
  type ContestResults,
  type ContestStanding,
  seasonCards,
  sideLabel,
  standingText,
  trayOrder,
  weekRows,
  weekSummary,
} from "@/lib/contest";
import { cn } from "@/lib/utils";

import { saveStanding } from "./actions";

// Results & standing (S-02, TASK-073; Contest Desktop `results`): your season against the model's
// top N, your league standing (entered by hand: the contest's site has no feed), this week so far
// and week by week. Every number is the response's; the picks lists are this week's.

const BUTTON = "inline-flex min-h-11 min-w-11 items-center justify-center gap-2 rounded-md px-3 text-label font-medium";
const OUTLINE = cn(BUTTON, "border border-input hover:bg-accent");

const FIELD =
  "min-h-11 w-24 rounded-md border border-input bg-background px-3 text-body text-foreground focus-visible:outline-2";

export function ResultsStanding({
  contestId,
  period,
  picks,
  results,
  standing,
  games,
  entries,
}: {
  contestId: number;
  /** The contest week; a new standing is entered for it */
  period: number;
  picks: number;
  results: ContestResults | null;
  standing: ContestStanding | null;
  games: readonly ContestGame[];
  entries: readonly ContestEntry[];
}) {
  if (results === null) {
    return (
      <p className="rounded-lg border bg-card px-4 py-10 text-center text-body text-muted-foreground">
        No results yet. They appear once this week&apos;s games are final.
      </p>
    );
  }
  const season = seasonCards(results, picks);
  const week = weekSummary(results.this_week);
  const rows = weekRows(results);
  const yours = trayOrder(entries).flatMap((e) => {
    const game = games.find((g) => g.id === e.game_id);
    return game ? [sideLabel(game, e.side)] : [];
  });
  const model = games.filter((g) => g.top_n && g.model).map((g) => sideLabel(g, g.model!.side));

  return (
    <div data-slot="results-standing" className="flex flex-col gap-4">
      <section aria-label="Season" className="grid gap-3 md:grid-cols-4">
        <Card label="You · season" value={season.you.record} note={season.you.rate} />
        <Card
          label={season.model ? `${season.model.label} · season` : "Model · season"}
          value={season.model?.record ?? "—"}
          note={season.model?.rate ?? "No model picks"}
        />
        <Card label="You vs model" value={season.diff} note="wins ahead or behind" />
        <StandingCard contestId={contestId} period={period} standing={standing} />
      </section>

      <section aria-label="This week so far" className="rounded-lg border bg-card p-4">
        <h2 className="mb-3 text-panel font-semibold">This week so far</h2>
        <div className="grid gap-4 md:grid-cols-2">
          <WeekSide label="You" side={week.you} picks={yours} />
          <WeekSide label={`Model's top ${picks}`} side={week.model} picks={model} />
        </div>
      </section>

      <section aria-label="Week by week" className="rounded-lg border bg-card p-4">
        <h2 className="mb-3 text-panel font-semibold">Week by week</h2>
        {rows.length === 0 ? (
          <p className="text-body text-muted-foreground">No finished weeks yet.</p>
        ) : (
          <div className="flex flex-col gap-4 md:flex-row md:items-start">
            <Chart rows={rows} />
            <table className="w-full text-body md:max-w-md">
              <thead>
                <tr className="text-left text-label text-muted-foreground">
                  <th className="py-1.5 font-medium">Week</th>
                  <th className="py-1.5 font-medium">You</th>
                  <th className="py-1.5 font-medium">Model</th>
                  <th className="py-1.5 text-right font-medium">±</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.label} data-slot="week-row" className="border-t">
                    <th scope="row" className="py-1.5 text-left font-medium">{r.label}</th>
                    <td className="py-1.5">{r.youRecord}</td>
                    <td className="py-1.5">{r.modelRecord}</td>
                    <td className="py-1.5 text-right">{r.diff}</td>
                  </tr>
                ))}
                <tr className="border-t font-semibold">
                  <th scope="row" className="py-1.5 text-left">Total</th>
                  <td className="py-1.5">{season.you.record}</td>
                  <td className="py-1.5">{season.model?.record ?? "—"}</td>
                  <td className="py-1.5 text-right">{season.diff}</td>
                </tr>
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function Card({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div data-slot="season-card" className="flex flex-col gap-0.5 rounded-lg border bg-card p-4">
      <span className="text-label text-muted-foreground">{label}</span>
      <span className="text-title font-semibold">{value}</span>
      <span className="text-caption text-muted-foreground">{note}</span>
    </div>
  );
}

function WeekSide({
  label,
  side,
  picks,
}: {
  label: string;
  side: { record: string; points: string; pending: number } | null;
  picks: string[];
}) {
  return (
    <div data-slot="week-side" className="flex flex-col gap-1">
      <div className="flex items-baseline gap-2">
        <span className="text-label text-muted-foreground">{label}</span>
        <span className="text-section font-semibold">{side?.points ?? "—"}</span>
        <span className="text-caption text-muted-foreground">
          {side ? `${side.record} · ${side.pending} pending` : "No model picks"}
        </span>
      </div>
      <p className="text-label text-muted-foreground">{picks.length > 0 ? picks.join(" · ") : "No picks yet"}</p>
    </div>
  );
}

function Chart({ rows }: { rows: ReturnType<typeof weekRows> }) {
  const width = 280;
  const height = 120;
  const top = Math.max(1, ...rows.flatMap((r) => [r.cumulativeYou, r.cumulativeModel]));
  const point = (i: number, v: number) =>
    `${rows.length === 1 ? width / 2 : (i / (rows.length - 1)) * width},${height - (v / top) * height}`;
  const line = (pick: (r: (typeof rows)[number]) => number) => rows.map((r, i) => point(i, pick(r))).join(" ");
  return (
    <figure className="flex flex-col gap-1">
      <svg
        role="img"
        aria-label="Cumulative wins by week, you and the model"
        viewBox={`-4 -4 ${width + 8} ${height + 8}`}
        className="h-32 w-full max-w-xs overflow-visible"
      >
        <polyline points={line((r) => r.cumulativeModel)} fill="none" strokeWidth={2} className="stroke-muted-foreground" />
        <polyline points={line((r) => r.cumulativeYou)} fill="none" strokeWidth={2} className="stroke-edge" />
      </svg>
      <figcaption className="flex gap-3 text-caption text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden className="h-0.5 w-3 bg-edge" /> You
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden className="h-0.5 w-3 bg-muted-foreground" /> Model
        </span>
      </figcaption>
    </figure>
  );
}

function StandingCard({
  contestId,
  period,
  standing,
}: {
  contestId: number;
  period: number;
  standing: ContestStanding | null;
}) {
  const text = standingText(standing);
  const [editing, setEditing] = useState(false);
  const [place, setPlace] = useState(standing ? String(standing.position) : "");
  const [field, setField] = useState(standing ? String(standing.field_size) : "");
  const [behind, setBehind] = useState(standing?.points_behind_leader == null ? "" : String(standing.points_behind_leader));
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  function save() {
    const pointsBehind = behind.trim() === "" ? null : Number(behind);
    startTransition(async () => {
      const result = await saveStanding(contestId, period, Number(place), Number(field), pointsBehind);
      if (result.kind === "saved") {
        setEditing(false);
        setError(null);
      } else {
        setError(result.message);
      }
    });
  }

  return (
    <div data-slot="standing" className="flex flex-col gap-1 rounded-lg border bg-card p-4">
      <span className="flex items-center gap-2 text-label text-muted-foreground">
        League standing
        {standing ? (
          <span className="rounded-sm border px-1 text-caption font-semibold tracking-wider uppercase">
            Entered by hand
          </span>
        ) : null}
      </span>
      {editing ? (
        <form
          className="flex flex-col gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            save();
          }}
        >
          <div className="flex flex-wrap gap-2">
            <label className="flex flex-col gap-0.5 text-caption text-muted-foreground">
              Place
              <input className={FIELD} inputMode="numeric" value={place} onChange={(e) => setPlace(e.target.value)} />
            </label>
            <label className="flex flex-col gap-0.5 text-caption text-muted-foreground">
              Of
              <input className={FIELD} inputMode="numeric" value={field} onChange={(e) => setField(e.target.value)} />
            </label>
            <label className="flex flex-col gap-0.5 text-caption text-muted-foreground">
              Pts back
              <input className={FIELD} inputMode="decimal" value={behind} onChange={(e) => setBehind(e.target.value)} />
            </label>
          </div>
          {error ? (
            <p role="alert" className="text-label text-neg">
              {error}
            </p>
          ) : null}
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={pending}
              className={cn(BUTTON, "bg-primary text-primary-foreground disabled:bg-secondary disabled:text-muted-foreground")}
            >
              <Check aria-hidden className="size-4" />
              Save
            </button>
            <button type="button" className={OUTLINE} onClick={() => setEditing(false)}>
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <>
          <span className="text-title font-semibold">{text?.place ?? "—"}</span>
          <span className="text-caption text-muted-foreground">{text?.behind ?? "Not entered yet"}</span>
          <button type="button" className={cn(OUTLINE, "mt-1 self-start")} onClick={() => setEditing(true)}>
            <Pencil aria-hidden className="size-3.5" />
            Edit standing
          </button>
        </>
      )}
    </div>
  );
}
