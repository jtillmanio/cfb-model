---
name: track-follow-ups
description: Finds follow-ups that merged PRs listed but nothing tracks, and places each where the work that will do it will read it (task files, roadmap, decisions log, planning docs, Owner checklist) on a docs/ branch with one PR. Also applies Owner checklist approvals the owner has ticked. Use when the user runs /track-follow-ups, after upgrading to kit 2.6, or asks to backfill, audit, or recover lost follow-ups.
argument-hint: "[--since <PR#|date>] [--dry-run]   e.g. --since 53  or  --since 2026-10-01 --dry-run"
---

# Track follow-ups: $ARGUMENTS

> **Doc roles:** names in **bold** such as **Architecture**, **Decisions**, or **Owner checklist** are roles in the "Project docs" table in `CLAUDE.md`. Always read and write the path the table gives for a role, including a `§ section` if it names one. If a role maps to `—`, follow the fallback in `classify.md`, or ask. Refer to sections by name, never by number.

> **Project overrides:** read `.claude/kit.json` first (`workflow.followUps`, `workflow.decisions`, `workflow.roadmap`, `largeFiles`), then `.claude/project/track-follow-ups.md` if it exists. It wins where it conflicts with this file, except that it can't lower the floor: never edit another task's acceptance criteria or a roadmap **Check:** line, never set anything `Ready`, never commit on or push to the base branch, and never make a change that needs approval without it.

The classification, bullet format, and approval rules are in `.claude/skills/track-follow-ups/classify.md`. Read it first and follow it; this file adds only what a backfill needs.

Parse `$ARGUMENTS`: `--since <PR#|date>` (default: the PR that installed the kit), `--dry-run` (report only; write nothing, create no branch).

## Phase 0: Preflight

1. On `workflow.baseBranch`, up to date (`git fetch`, then `git status -sb` shows no "behind"), clean tree (`git status --porcelain` empty). Otherwise stop. The branch comes later; the scan must see what's merged.
2. `gh auth status` succeeds. Otherwise stop: the merged PR bodies come from GitHub.
3. If `workflow.followUps` is `propose`, this run is `--dry-run`: say so.

## Phase 1: Ticked approvals

Read the **Owner checklist**'s Approvals. Every ticked item that has no "→ <where it went>" yet is approved work waiting to be done: make the change as described (destination 5 or 6 in `classify.md`), and note it for Phase 4. Unticked items stay as they are.

## Phase 2: Collect

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/list-follow-ups.ps1 [-Since <n|date>] -AsJson
```

It prints each merged PR since the cutoff with its Follow-ups bullets and any destination a bullet already names. Report the cutoff it used, and why.

## Phase 3: Decide what is already handled

For each bullet, find evidence, cheapest first, and record it in the table below. Use the bullet's distinctive words (identifiers, error names, file names, IDs) as Grep patterns, not the whole sentence.

| Check | How | Result |
|---|---|---|
| The bullet names a destination | Open that path and section; the note (or its substance) is there | **tracked** (where) |
| Tracked somewhere else | Grep the roadmap, `docs/tasks/` and `docs/tasks/archive/`, the **Task list**, the **Decisions** log, the **Owner checklist**, and the planning docs (Features, Architecture, Data model, Domain specs) | **tracked** (where) |
| Done since | The code or repo shows it: the file exists or was deleted (`git ls-files`, `git log --oneline -S '<identifier>'`), the behaviour is in the code with a test, a later PR's What says so, a secret exists (`gh secret list`; names only), a task that covered it is Done | **done** (evidence) |
| Accepted or declined | The PR, or a later PR or decision, says the owner accepted it as is or said not to track it | **not tracked** (reason) |
| Duplicate | Same item in an earlier PR's list | merge into the first one |

Everything else is **open**. When the evidence is partial (a task exists but doesn't mention the detail), the item is open and goes to that task (destination 2).

## Phase 4: Classify and report

Classify each open item with `classify.md` (destination 1 doesn't exist here: the task that noticed it is merged, so a small fix goes to the task that will next touch that code, or becomes new work). Then show one table, under 40 rows per screen:

`PR | Follow-up | Status (tracked / done / not tracked / open) | Destination or evidence | Needs approval`

followed by the ticked approvals from Phase 1. With `--dry-run`, stop here.

Then follow `workflow.followUps`: with `review`, stop and wait for the owner's approval of the table. With `apply` (default), continue; the PR is the review. Items that need approval (planning docs, `propose` decisions) are asked about in one numbered list in this message; the owner's answers decide which are written now, and the rest are queued in the Owner checklist's Approvals.

## Phase 5: Apply on a branch

1. `git switch -c docs/track-follow-ups-<YYYY-MM-DD>`.
2. Write each placement, as `classify.md` says. Notes in task files are headed with the PR that noticed them: `*From #62 (task 1.2):* …`. For decisions, use `next-id.ps1`; for new roadmap items, `next-id.ps1 -List`.
3. Tick each Phase 1 approval with where it went: `- [x] … → docs/architecture.md § Search (this PR)`.
4. Unless `workflow.archiveDone` is `false`, run `.claude/scripts/archive-done.ps1` (it stages Done task renames).
5. Stage by path, read `git diff --staged`, and commit: `docs: track follow-ups from PRs #53–#70` (`area`: `docs: track follow-ups from PRs 53-70`).
6. Push and open the PR (`gh pr create --base <base> --title "<the subject>" --body-file <temp file outside the repo>`). Body:
   - **What**: the cutoff, how many PRs and follow-ups were read, and counts per status.
   - **Follow-ups**: every follow-up from every PR, grouped by PR, each ending `→ <path> § <section>` or `→ not tracked: <reason>` (done items: `→ not tracked: done in #64 (<evidence>)`; already tracked: `→ not tracked: already in <path> § <section>`).
   - **Approvals**: applied ones, and the ones queued in the Owner checklist.
   - **How it was verified**: `build-index.ps1` exits 0, and a spec-reviewer run in follow-ups mode (below).
7. Delegate **spec-reviewer** in follow-ups mode: "Follow-ups check only; no task file. The Follow-ups list is the PR body at <temp file>; the diff is `git diff <base>...HEAD`." Fix what it flags, commit, push.

## Final report (under 20 lines)

PR link; counts (tracked, done, not tracked, newly placed, approvals applied, approvals queued); the items that need the owner, each with its checklist line; then `workflow.afterMerge` if set. Never merge.
