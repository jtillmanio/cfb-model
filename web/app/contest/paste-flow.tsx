"use client";

import {
  Check,
  CheckCheck,
  CircleAlert,
  ClipboardPaste,
  Eraser,
  LoaderCircle,
  Lock,
  Minus,
} from "lucide-react";
import { type ReactNode, useEffect, useRef, useState, useTransition } from "react";

import {
  aliasMappings,
  canConfirm,
  type ContestRules,
  type ImportPreview,
  type ImportRow,
  type ImportTeam,
  importSummary,
  lockNote,
  namesToPick,
  type Picks,
  rawLines,
  refusalCopy,
  type RefusalCopy,
  rowKickoff,
  rowLine,
  rowSource,
  rowSport,
  rowState,
  rowStatus,
  sideLine,
  teamName,
  type Tone,
} from "@/lib/contest";
import { cn } from "@/lib/utils";

import { confirmImport, previewImport } from "./actions";
import { RepasteDiff } from "./repaste-diff";
import { TeamDot, TeamPicker } from "./team-picker";

// The Contest paste flow (S-02, TASK-072; Contest Desktop `empty` / `parse`, Contest Mobile;
// C2a, C2b, C2e). Paste the contest page → the API's rows beside the raw text → pick a team for
// each name it couldn't match → Confirm saves the picks as aliases and the week's lines, and the
// page refreshes into the confirmed week (TASK-073 ranks it). Nothing is saved before Confirm.
//
// Left out, on purpose: the board's "Skip it, confirm 9" (the API saves every row or none, D-172),
// "Add game manually" (out of scope) and the parsed table's Market column (not in the preview).

type Mode = "closed" | "paste" | "parsed";

const SPORT: Record<string, string> = { cfb: "CFB", nfl: "NFL" };
const TONE: Record<Tone, string> = { muted: "text-muted-foreground", pos: "text-pos", neg: "text-neg" };
const LINE_PX = 18; // the raw paste's line height (h-4.5)

const BUTTON = "inline-flex min-h-11 items-center justify-center gap-2 rounded-md px-3 text-label font-medium";
const PRIMARY = cn(BUTTON, "bg-primary text-primary-foreground disabled:bg-secondary disabled:text-muted-foreground");
const OUTLINE = cn(BUTTON, "border border-input hover:bg-accent");
const QUIET = cn(BUTTON, "text-muted-foreground hover:bg-accent hover:text-foreground");

export function PasteFlow({
  contestId,
  period,
  rules,
  hero,
  source,
  weekOpen = true,
  children,
}: {
  contestId: number;
  /** The contest week the paste is for (the page prints none, D-172). */
  period: number;
  rules: ContestRules;
  /** The week has no slate yet: open on the paste box. */
  hero: boolean;
  /** The confirmed week's toolbar, e.g. "From Splash paste · Thu 10:00 PM · 10 games". */
  source?: string;
  /** Some game is still open, so the week's lines can be re-pasted. */
  weekOpen?: boolean;
  /** The confirmed week. */
  children?: ReactNode;
}) {
  const [mode, setMode] = useState<Mode>(hero ? "paste" : "closed");
  const [text, setText] = useState("");
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [picks, setPicks] = useState<Picks>({});
  const [refusal, setRefusal] = useState<RefusalCopy | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [hint, setHint] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();
  const box = useRef<HTMLTextAreaElement>(null);

  function read(pasted: string) {
    setText(pasted);
    setRefusal(null);
    setError(null);
    setHint(null);
    if (pasted.trim() === "") return;
    startTransition(async () => {
      const result = await previewImport(contestId, period, pasted);
      if (result.kind === "preview") {
        setPreview(result.preview);
        setPicks({});
        setMode("parsed");
      } else if (result.kind === "refused") {
        setRefusal(refusalCopy(result.refusal, pasted, rules.sports));
      } else {
        setError(result.message);
      }
    });
  }

  async function fromClipboard() {
    try {
      const pasted = await navigator.clipboard.readText();
      if (pasted.trim() === "") setHint("The clipboard is empty. Copy the contest page first.");
      else read(pasted);
    } catch {
      setHint("Your browser didn't let us read the clipboard: click the box and press Ctrl+V (⌘V on a Mac).");
      box.current?.focus();
    }
  }

  function clear() {
    setText("");
    setRefusal(null);
    setError(null);
    setHint(null);
    box.current?.focus();
  }

  function confirm() {
    if (!preview) return;
    setError(null);
    startTransition(async () => {
      const result = await confirmImport(contestId, period, text, aliasMappings(preview, picks));
      if (result.kind === "confirmed") return; // the page refreshes into the confirmed week
      if (result.kind === "refused") {
        setError(result.refusal.message);
        const again = await previewImport(contestId, period, text);
        if (again.kind === "preview") {
          setPreview(again.preview);
          setPicks({});
        }
      } else {
        setError(result.message);
      }
    });
  }

  if (mode === "closed") {
    return (
      <>
        <div data-slot="week-toolbar" className="mb-3 flex flex-wrap items-center gap-2.5">
          <span className="text-caption text-muted-foreground">{source}</span>
          <span className="flex-1" />
          {weekOpen ? (
            <button type="button" className={OUTLINE} onClick={() => setMode("paste")}>
              <ClipboardPaste aria-hidden className="size-3.5" />
              Re-paste to update lines
            </button>
          ) : (
            <span className="inline-flex min-h-11 items-center gap-1.5 rounded-md bg-muted px-3 text-label font-medium text-locked">
              <Lock aria-hidden className="size-3.5" />
              Week {period} closed · results after the last game
            </span>
          )}
        </div>
        {children}
      </>
    );
  }

  if (mode === "parsed" && preview) {
    return (
      <Parsed
        preview={preview}
        text={text}
        rules={rules}
        picks={picks}
        setPicks={setPicks}
        error={error}
        pending={pending}
        onAgain={() => {
          setPreview(null);
          clear();
          setMode("paste");
        }}
        onConfirm={confirm}
      />
    );
  }

  return (
    <section
      aria-labelledby="paste-title"
      aria-busy={pending || undefined}
      className="mx-auto flex w-full max-w-220 flex-col gap-5 rounded-lg border bg-card p-4 md:p-7"
    >
      <div className="flex flex-col gap-3.5 md:flex-row md:items-start md:gap-4">
        <span className="flex size-11 shrink-0 items-center justify-center rounded-lg border bg-muted">
          <ClipboardPaste aria-hidden className="size-5" />
        </span>
        <div className="flex min-w-0 flex-col gap-1">
          <h2 id="paste-title" className="text-section font-semibold md:text-title">
            Paste from Splash
          </h2>
          <p className="max-w-155 text-body text-muted-foreground">
            {hero ? `No Week ${period} slate yet. ` : `Update Week ${period}'s lines. `}
            <span className="md:hidden">
              On the Splash contest page, tap and hold → Select All → Copy. Then come back here.
            </span>
            <span className="max-md:hidden">
              Paste the contest page and we&apos;ll match every team, read each spread and kickoff, and rank the
              games against the contest&apos;s own lines.
            </span>
          </p>
        </div>
        {!hero ? (
          <button type="button" className={cn(QUIET, "md:ml-auto")} onClick={() => setMode("closed")}>
            Cancel
          </button>
        ) : null}
      </div>

      <ol className="hidden grid-cols-3 gap-2.5 md:grid">
        <Step n={1}>
          Open the league&apos;s <b className="font-semibold">Pick against the spread</b> page on Splash
        </Step>
        <Step n={2}>
          Select all <Key>⌘A</Key> and copy <Key>⌘C</Key>
        </Step>
        <Step n={3}>
          Click the box below and paste <Key>⌘V</Key>
        </Step>
      </ol>

      <button type="button" className={cn(PRIMARY, "min-h-13 text-panel font-semibold md:hidden")} onClick={fromClipboard}>
        <ClipboardPaste aria-hidden className="size-4.5" />
        Paste from clipboard
      </button>

      <div className="relative h-38 overflow-hidden rounded-lg border-2 border-dashed border-input bg-background hover:border-ring md:h-70">
        <textarea
          ref={box}
          aria-label="The contest page's text"
          value={text}
          spellCheck={false}
          placeholder={PLACEHOLDER}
          onChange={(e) => setText(e.target.value)}
          onPaste={(e) => {
            e.preventDefault();
            read(e.clipboardData.getData("text"));
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
              e.preventDefault();
              read(text);
            }
          }}
          className="absolute inset-0 size-full resize-none bg-transparent px-3 py-3 font-mono text-caption text-foreground outline-none md:px-4.5 md:py-4"
        />
        <div className="pointer-events-none absolute right-4.5 bottom-4.5 hidden flex-col items-end gap-2 md:flex">
          <span className="pointer-events-auto flex items-center gap-2">
            {text.trim() !== "" && !refusal && !pending ? (
              <button type="button" className={cn(OUTLINE, "bg-card")} onClick={() => read(text)}>
                Read this text
              </button>
            ) : null}
            <button type="button" className={cn(PRIMARY, "text-body font-semibold")} disabled={pending} onClick={fromClipboard}>
              {pending ? (
                <LoaderCircle aria-hidden className="size-4 animate-spin motion-reduce:animate-none" />
              ) : (
                <ClipboardPaste aria-hidden className="size-4" />
              )}
              {pending ? "Reading…" : "Paste from clipboard"}
            </button>
          </span>
          <span className="text-caption text-muted-foreground">or click anywhere in the box and press ⌘V</span>
        </div>
      </div>
      {pending ? (
        <p role="status" className="text-caption text-muted-foreground md:hidden">
          Reading the paste…
        </p>
      ) : null}
      {hint ? <p className="text-caption text-muted-foreground">{hint}</p> : null}

      {refusal ? (
        <Alert title={refusal.title} meta={refusal.meta}>
          {refusal.body}
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <button type="button" className={cn(BUTTON, "bg-secondary text-secondary-foreground")} onClick={clear}>
              <Eraser aria-hidden className="size-3.5" />
              Clear and paste again
            </button>
          </div>
        </Alert>
      ) : null}
      {error ? <Alert title="The paste wasn't read">{error}</Alert> : null}

      <div className="grid gap-4 text-caption md:grid-cols-2">
        <p className="flex gap-2">
          <Check aria-hidden className="mt-0.5 size-3.5 shrink-0 text-pos" />
          <span>
            <b className="font-semibold">We read</b>{" "}
            <span className="text-muted-foreground">
              team names, each side&apos;s spread, kickoff day and time, and the &ldquo;Picks lock&rdquo; deadline.
              Sport is inferred (Splash shows NFL teams by nickname).
            </span>
          </span>
        </p>
        <p className="flex gap-2">
          <Minus aria-hidden className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" />
          <span>
            <b className="font-semibold">We skip</b>{" "}
            <span className="text-muted-foreground">
              totals (Over/Under), team records, AP ranks, scores of finished games and the page&apos;s column
              headers.
            </span>
          </span>
        </p>
      </div>
    </section>
  );
}

const PLACEHOLDER = [
  "Pick against the spread",
  "Picks lock:",
  "Sun, Oct 11, 2026, 8:20 PM",
  "PICKS",
  "PTS",
  "STATUS",
  "GAME DETAILS",
  "Friday, Oct 9",
  "UNLV",
  "Boise State",
  "Preview",
  "Fri 8:00pm",
  "…",
].join("\n");

function Step({ n, children }: { n: number; children: ReactNode }) {
  return (
    <li className="flex items-center gap-2.5 rounded-lg border px-3 py-2.5 text-label">
      <span className="flex size-5.5 shrink-0 items-center justify-center rounded-full bg-secondary text-caption font-bold">
        {n}
      </span>
      <span>{children}</span>
    </li>
  );
}

function Key({ children }: { children: string }) {
  return <kbd className="rounded-sm border bg-muted px-1.25 py-px font-mono text-caption font-medium">{children}</kbd>;
}

function Alert({ title, meta, children }: { title: string; meta?: string; children: ReactNode }) {
  return (
    <div role="alert" className="flex gap-3 rounded-md border border-destructive bg-destructive/8 px-4 py-3.5">
      <CircleAlert aria-hidden className="mt-0.5 size-5 shrink-0 text-destructive" />
      <div className="flex min-w-0 flex-1 flex-col gap-1.5">
        <p className="text-panel font-semibold">{title}</p>
        <div className="flex flex-col gap-1.5 text-label">{children}</div>
        {meta ? <p className="text-caption text-muted-foreground">{meta}</p> : null}
      </div>
    </div>
  );
}

// The parsed preview

function pickedTeam(row: ImportRow, name: string | null, picks: Picks): ImportTeam | null {
  if (name === null || !(name in picks)) return null;
  const entry = row.unmatched.find((n) => n.name === name);
  return entry?.candidates.find((t) => t.id === picks[name]) ?? null;
}

function Parsed({
  preview,
  text,
  rules,
  picks,
  setPicks,
  error,
  pending,
  onAgain,
  onConfirm,
}: {
  preview: ImportPreview;
  text: string;
  rules: ContestRules;
  picks: Picks;
  setPicks: (picks: Picks) => void;
  error: string | null;
  pending: boolean;
  onAgain: () => void;
  onConfirm: () => void;
}) {
  const firstNeeds = preview.rows.find((r) => rowState(r, picks) === "needs")?.index ?? preview.rows[0]?.index ?? 0;
  const [selected, setSelected] = useState(firstNeeds);
  const summary = importSummary(preview, picks);
  const ready = canConfirm(preview, picks);
  const note = lockNote(preview, rules);
  const lines = rawLines(text, preview.rows, picks);
  const left = preview.rows.filter((r) => !["matched", "fixed"].includes(rowState(r, picks))).length;

  return (
    <div data-slot="paste-parsed" aria-busy={pending || undefined} className="flex flex-col gap-3">
      <div className="flex flex-col gap-2 rounded-lg border bg-card px-3.5 py-3 md:flex-row md:items-center md:gap-4 md:px-4">
        <div className="flex min-w-0 flex-col gap-1">
          <p className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
            <span className="text-body font-semibold">{summary.found}</span>
            <span className="text-label text-muted-foreground">
              {[summary.dates, summary.sports].filter(Boolean).join(" · ")}
            </span>
          </p>
          <p data-slot="match-summary" className="flex flex-wrap items-center gap-1.5 text-label font-semibold">
            <Check aria-hidden className="size-3.5 text-pos" />
            <span>{summary.matched}</span>
            {summary.unmatched ? (
              <>
                <span className="text-muted-foreground">{" · "}</span>
                <span className="text-neg">{summary.unmatched}</span>
              </>
            ) : null}
          </p>
          {note ? <p className="text-caption text-muted-foreground">{note}</p> : null}
        </div>
        <span className="flex-1" />
        <button type="button" className={cn(QUIET, "self-start md:self-auto")} onClick={onAgain}>
          Paste again
        </button>
      </div>

      <RepasteDiff preview={preview} />

      <div className="grid items-start gap-3 xl:grid-cols-[380px_minmax(0,1fr)]">
        <RawPaste lines={lines} selected={selected} rows={preview.rows} />

        <section
          aria-label="Parsed slate"
          className="flex min-w-0 flex-col overflow-hidden rounded-lg border bg-card"
        >
          <div className="flex min-h-10 items-center gap-2 border-b px-3">
            <h2 className="text-label font-semibold">Parsed slate</h2>
            <span className="text-caption text-muted-foreground max-md:hidden">
              Click a row&apos;s source to see where it came from
            </span>
          </div>
          <div className="hidden h-7.5 grid-cols-[64px_44px_96px_minmax(0,1fr)_96px_120px] items-center gap-x-2.5 border-b px-3 text-caption font-medium text-muted-foreground md:grid">
            <span>Source</span>
            <span>Sport</span>
            <span>Kickoff ET</span>
            <span>Matchup</span>
            <span className="text-right">Contest</span>
            <span>Status</span>
          </div>
          <ul>
            {preview.rows.map((row) => (
              <ParsedRow
                key={row.index}
                row={row}
                picks={picks}
                selected={row.index === selected}
                onSelect={() => setSelected(row.index)}
                onPick={(name, team) => {
                  const next = { ...picks };
                  if (team) next[name] = team.id;
                  else delete next[name];
                  setPicks(next);
                }}
              />
            ))}
          </ul>
          {error ? (
            <div className="px-3 pt-3">
              <Alert title="The slate wasn't saved">{error}</Alert>
            </div>
          ) : null}
          <div className="flex flex-col gap-2 p-3 md:flex-row md:items-center md:gap-3">
            <p className="flex-1 text-caption text-muted-foreground">
              Re-pasting later only updates lines and kickoffs. Picks you&apos;ve made keep the line they were
              locked in at.
            </p>
            <button
              type="button"
              className={cn(PRIMARY, "px-4 text-body font-semibold max-md:min-h-12.5")}
              disabled={!ready || pending}
              onClick={onConfirm}
            >
              {pending ? (
                <LoaderCircle aria-hidden className="size-4 animate-spin motion-reduce:animate-none" />
              ) : (
                <Check aria-hidden className="size-4" />
              )}
              {pending ? "Saving…" : `Confirm ${summary.games} game${summary.games === 1 ? "" : "s"}`}
            </button>
            {!ready ? (
              <p className="text-center text-caption text-muted-foreground md:hidden">
                Fix {left} game{left === 1 ? "" : "s"} to confirm all {summary.games}
              </p>
            ) : null}
          </div>
        </section>
      </div>
    </div>
  );
}

function RawPaste({ lines, selected, rows }: { lines: ReturnType<typeof rawLines>; selected: number; rows: readonly ImportRow[] }) {
  const scroller = useRef<HTMLDivElement>(null);
  const first = rows.find((r) => r.index === selected)?.first_line ?? 1;
  useEffect(() => {
    if (scroller.current) scroller.current.scrollTop = Math.max(0, (first - 5) * LINE_PX);
  }, [first]);

  const body = (
    <div ref={scroller} className="h-153 overflow-auto py-1.5 font-mono text-caption max-xl:h-90">
      {lines.map((l) => (
        <div
          key={l.n}
          data-slot="raw-line"
          data-read={l.read || undefined}
          className={cn(
            "grid h-4.5 grid-cols-[38px_minmax(0,1fr)] gap-x-2 pr-2.5 leading-4.5",
            l.row === selected && l.row !== null && "bg-accent",
          )}
        >
          <span className="text-right text-muted-foreground select-none">{l.n}</span>
          <span
            className={cn(
              "overflow-hidden text-ellipsis whitespace-pre",
              l.bad ? "text-neg underline decoration-neg decoration-wavy underline-offset-3" : l.read ? "text-foreground" : "text-input",
            )}
          >
            {l.text || " "}
          </span>
        </div>
      ))}
    </div>
  );
  const legend = (
    <span className="flex items-center gap-2.5 text-caption text-muted-foreground">
      <span className="flex items-center gap-1">
        <span aria-hidden className="size-2 rounded-xs bg-foreground" />
        read
      </span>
      <span className="flex items-center gap-1">
        <span aria-hidden className="size-2 rounded-xs bg-input" />
        skipped
      </span>
    </span>
  );

  return (
    <>
      <section
        aria-label="Your paste"
        data-slot="raw-paste"
        className="hidden min-w-0 flex-col overflow-hidden rounded-lg border bg-card xl:flex"
      >
        <div className="flex h-10 items-center gap-2 border-b px-3">
          <h2 className="text-label font-semibold">Your paste</h2>
          <span className="text-caption text-muted-foreground">{lines.length} lines</span>
          <span className="flex-1" />
          {legend}
        </div>
        {body}
      </section>
      <details data-slot="raw-paste-disclosure" className="rounded-lg border bg-card xl:hidden">
        <summary className="flex min-h-11 cursor-pointer items-center gap-2 px-3 text-label font-semibold">
          Your paste
          <span className="font-normal text-muted-foreground">{lines.length} lines</span>
          <span className="flex-1" />
          {legend}
        </summary>
        <div className="border-t">{body}</div>
      </details>
    </>
  );
}

function ParsedRow({
  row,
  picks,
  selected,
  onSelect,
  onPick,
}: {
  row: ImportRow;
  picks: Picks;
  selected: boolean;
  onSelect: () => void;
  onPick: (name: string, team: ImportTeam | null) => void;
}) {
  const state = rowState(row, picks);
  const status = rowStatus(row, picks);
  const sport = rowSport(row);
  const away = row.away_team ?? pickedTeam(row, row.away_name, picks);
  const home = row.home_team ?? pickedTeam(row, row.home_name, picks);
  const needs = state === "needs";
  const StatusIcon = state === "fixed" ? CheckCheck : status.tone === "neg" ? CircleAlert : Check;

  return (
    <li
      data-slot="parsed-row"
      data-state={state}
      className={cn(
        "border-b",
        needs && "bg-neg/7 ring-1 ring-neg ring-inset",
        selected && !needs && "bg-accent",
      )}
    >
      <div className="grid grid-cols-[44px_minmax(0,1fr)_auto] items-center gap-x-2.5 gap-y-1 px-3 py-2 md:min-h-14 md:grid-cols-[64px_44px_96px_minmax(0,1fr)_96px_120px] md:py-0">
        <button
          type="button"
          onClick={onSelect}
          aria-label={`Show lines ${rowSource(row).slice(1)} in the paste`}
          className={cn(
            "min-h-11 justify-self-start font-mono text-caption font-medium max-md:hidden",
            needs ? "text-neg" : "text-muted-foreground",
          )}
        >
          {rowSource(row)}
        </button>
        <span
          className={cn(
            "justify-self-start rounded-sm px-1 text-caption font-semibold tracking-wider",
            sport ? "bg-secondary" : "border border-dashed border-input text-muted-foreground",
          )}
        >
          {sport ? (SPORT[sport] ?? sport.toUpperCase()) : "?"}
        </span>
        <span className="text-label whitespace-nowrap max-md:hidden">{rowKickoff(row)}</span>
        <div className="flex min-w-0 flex-col gap-0.5">
          <Side team={away} raw={row.away_name} missing={needs && !away} />
          <Side team={home} raw={row.home_name} missing={needs && !home} />
          <span className="text-caption text-muted-foreground md:hidden">
            {rowKickoff(row)} · {rowLine(row)}
          </span>
        </div>
        <span className="text-right text-label font-semibold whitespace-nowrap max-md:hidden">{rowLine(row)}</span>
        <span className={cn("flex items-center gap-1.25 text-caption font-medium", TONE[status.tone])}>
          <StatusIcon aria-hidden className="size-3.25 shrink-0" />
          <span className={cn(state === "matched" && "max-md:sr-only")}>{status.text}</span>
          {state === "fixed" ? (
            <button
              type="button"
              className="ml-1 min-h-11 text-muted-foreground underline underline-offset-2 hover:text-foreground"
              onClick={() => namesToPick(row).forEach((name) => onPick(name, null))}
            >
              Change
            </button>
          ) : null}
        </span>
      </div>
      {needs ? (
        <div className="flex flex-col gap-2.5 px-3 pb-3.5 md:pl-30">
          <p className="text-caption text-muted-foreground">
            We couldn&apos;t match {row.unmatched.length === 1 ? "this name" : "these names"}. Pick the{" "}
            {row.unmatched.length === 1 ? "team" : "teams"}; the spread and kickoff were read fine.
          </p>
          <div className="grid items-start gap-3 md:grid-cols-2">
            {row.unmatched.map((n) => {
              const side = n.name === row.away_name ? "away" : "home";
              return (
                <TeamPicker
                  key={n.name}
                  name={n.name}
                  side={side === "away" ? "Away" : "Home"}
                  line={sideLine(row, side)}
                  candidates={n.candidates}
                  picked={pickedTeam(row, n.name, picks)}
                  onPick={(team) => onPick(n.name, team)}
                />
              );
            })}
          </div>
          <p className="text-caption text-muted-foreground">
            Confirm saves {row.unmatched.length === 1 ? "this name" : "these names"} for future pastes.
          </p>
        </div>
      ) : null}
    </li>
  );
}

function Side({ team, raw, missing }: { team: ImportTeam | null; raw: string | null; missing: boolean }) {
  if (raw === null) return <span className="text-label text-muted-foreground">Couldn&apos;t read this block</span>;
  if (missing || !team) {
    return (
      <span className="flex min-w-0 items-center gap-1.5">
        <span aria-hidden className="size-4 shrink-0 rounded-full border border-dashed border-neg" />
        <span className="text-label font-medium text-neg">“{raw}”</span>
        <span className="text-caption text-muted-foreground">no match</span>
      </span>
    );
  }
  const name = teamName(team);
  return (
    <span className="flex min-w-0 items-center gap-1.5">
      <TeamDot color={team.color} />
      <span className="truncate text-label font-medium">{name}</span>
      {raw !== name ? <span className="text-caption whitespace-nowrap text-muted-foreground">“{raw}”</span> : null}
    </span>
  );
}
