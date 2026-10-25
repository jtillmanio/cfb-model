# Follow-ups: classify, place, approve

The one home for follow-up tracking. `/implement-task` (plan gate, close-out, Blocked path), `/plan-batch`, `/skeleton`, and `/track-follow-ups` follow this file; none of them restates it.

> **Doc roles:** names in **bold** are roles in the "Project docs" table in `CLAUDE.md`. Read and write the path the table gives, including a `§ section`. A role mapped to `—` uses the fallback stated below.

A **follow-up** is work noticed during a task and deliberately left out of it. The aim: every follow-up is written where the work that will do it will read it, in the same PR that noticed it, and the PR says where each one went, so the owner reviews the placement in the PR and nothing depends on someone re-reading a merged PR body.

## The switch

`workflow.followUps` in `.claude/kit.json`. A missing key means `apply`.

| Value | Attended | Unattended |
|---|---|---|
| `apply` (default) | Write each placement in the close-out commit. Stop only for items that need approval (below), asked together with the close-out question | Write each placement that needs no approval; queue the rest in the **Owner checklist** |
| `review` | Show every planned placement at the gate and wait; then write the approved ones | Behave as `propose` |
| `propose` | Write nothing outside this task's own file and its roadmap entry. Each PR bullet names its intended destination, marked `(proposed)` | Same |

**Owner wins.** When the owner says "don't track X" (in the session, in the PR, or in `.claude/project/<skill>.md` for a whole category), X ends `→ not tracked: owner said not to`. When the owner changes a placement, use theirs.

## Decisions mode

Candidate decisions follow `workflow.decisions` when it is set, and `workflow.followUps` when it isn't (`apply` → `append`, `review` → `append` after the review stop, `propose` → `propose`). An explicit `decisions` value always wins.

- `append`: record it (destination 5).
- `propose`: the decision needs the owner's approval before Claude records it. Attended: ask at the gate ("Record D-24: …?"); on yes, record it exactly as `append` does. Unattended, or no answer: queue it in the **Owner checklist** as an approval.

## Where each follow-up goes

Take the first destination that fits. Each follow-up gets exactly one; a decision or new item may carry the doc updates it implies (destination 6) on the same bullet.

1. **This task.** Small and inside the task's scope (its Goal, ACs, or roadmap entry): it isn't a follow-up. Do it now as a plan revision (`/implement-task` Phase 2 rule), with the owner's OK in attended mode. Unattended sessions never widen the plan: use destination 2–4 instead and add "(could be done in <git ID>)". A typo in this task's own roadmap entry or task file counts as this task, except the **Check:** line and the ACs, which are the owner's: propose the fix and ask. Bullet: `→ not tracked: done in this PR (plan revision)` for code; for a fix to this task's roadmap entry or another doc, name it so the edit traces: `→ docs/TASKS.md § 1.3 (fixed in this PR)`.
2. **An existing task that isn't Done** (in `docs/tasks/`, status Draft, Ready, In progress, Review, or Blocked). Append a bullet to its `## Context`:
   - `- *From TASK-004 (task/1.3-bulk-parser):* <the note>`; in roadmap mode name the roadmap ID too: `*From TASK-004 (1.3, task/1.3-bulk-parser):*`. After the PR is opened, the branch name is replaced with `PR #n` (see Link commit).
   - Never add to, edit, or reorder its acceptance criteria, Out of scope, or Plan. Those are the owner's.
   - If the note raises a question, write it as one for that task's plan: `*From TASK-004 (…), open question for the plan:* <question>`.
   - If that task's plan is already approved, end the bullet with "(arrived after the plan was approved)". `/implement-task` preflight treats it as a stale plan.
   - Bullet: `→ docs/tasks/TASK-005-range-errors.md § Context`.
3. **Roadmap mode: a roadmap item with no task file yet** (no task title starts with its ID). Add a sentence or sub-bullet to that item's body in the roadmap. Never touch its **Check:** line (`workflow.roadmap.checkLabel`) or its checkbox. Bullet: `→ docs/TASKS.md § 1.4`.
4. **New work.**
   - Roadmap mode: add an item in the phase it belongs to, with the next free ID in that phase (`next-id.ps1 -List`, below), a size, and a **Check:** line written to the `/new-task` AC rules (observable result, expected value). If the roadmap has a build-order table, place it there too. The Check is a proposal: say so in the PR, so the owner agrees it by merging or edits it first (`/new-task` then copies it verbatim). Bullet: `→ docs/TASKS.md § 1.9 (new)`.
   - Otherwise: create the task file the way `/new-task` does (next free TASK ID, every template section, `status: Draft`), and add its stub to the **Task list** under the milestone it belongs to, with the TASK ID. Bullet: `→ docs/tasks/TASK-031-….md (new, Draft)`.
   - Either way new work is never `Ready` and never gets a task file in roadmap mode: the owner promotes it.
5. **A candidate decision** (new dependency, pattern, schema convention, rejected approach, a rule the owner stated): follow the decisions mode above. To record one:
   - take the ID from `next-id.ps1` (below), never "highest in this file + 1": another open branch may have taken it;
   - append the row in the log's own format; if the log has a "next new decision" line, update it;
   - if it changes an earlier decision, add "Amended by D-n" to that row (the only edit to an old row) and fix any `.claude/rules/` file or `CLAUDE.md` hard rule that states the old rule;
   - list the planning docs it contradicts as destination-6 updates on the same bullet.
   - Bullet: `→ docs/decisions.md § D-24` (append) or `→ <Owner checklist> § Approvals` (queued).
6. **A planning doc that is now wrong or incomplete**: **Features**, **Screen inventory**, **Architecture**, **Data model**, **Domain specs**, **Design brief**, a `.claude/rules/` file. These say what the product is, so the edit needs the owner's approval (see Approvals). Once approved, edit the doc in its own words; if the change describes work not built yet, say so inline ("(planned: TASK-031)", "(roadmap 1.9)"). Never change a number the source data owns: correct the prose. Bullet: `→ docs/architecture.md § Search`.
7. **An action only the owner can take** (a secret, a dashboard or hosting setting, a purchase, a production data fix): add it to the **Owner checklist** under its actions. Bullet: `→ <Owner checklist> § Actions`.
8. **No action needed** (informational, already done, accepted as is, a duplicate of a tracked item): it stays in the PR. Bullet: `→ not tracked: <reason>`, e.g. `already tracked in TASK-007 § Context`, `accepted as is by the owner`.

## Approvals

Destination 6, and destination 5 under `propose`, need the owner's yes before anything is written. There are two gates where the owner sees follow-ups, and an approval at either one is acted on, so approved work is documented where it will be completed:

- **Before development: the plan gate** (`/implement-task` Phase 1, the `/plan-batch` hand-off). Planning often finds doc drift, a question for another task, or a missing roadmap item. List them under "Follow-ups" in the plan, each with its planned placement. Approving the plan approves those placements unless the owner strikes one. Record them in the task file's `## Follow-ups` straight away (marked `(approved at plan)`); they are written to their destinations at close-out with the rest. `/plan-batch` writes them on the plans branch, since that PR is its close-out.
- **After development: close-out** (`/implement-task` Phase 6). One message: the placements that need approval, as a numbered list, then "Push and open a draft PR?". The owner answers per item ("approve 1, 3; skip 2"); approved items are written in the close-out commit.
- **Queued approvals.** An item not approved in the session (unattended, or the owner didn't answer) goes into the **Owner checklist** under an Approvals heading, one unticked box each: `- [ ] Update docs/architecture.md § Search: suggestions use pg_trgm similarity ≥ 0.3 (from TASK-004, PR #70)`. When the owner ticks it, or says "approve <item>" in any session, the change is made in that session on a branch (or by the next `/track-follow-ups` run), and the item is ticked with where it went: `- [x] … → docs/architecture.md § Search (PR #74)`.
- **No Owner checklist** (role `—`): attended, offer to create one from `docs/templates/owner-checklist.md` and add the row to the Project docs table. Unattended: the bullet ends `→ not tracked: needs approval, and there is no Owner checklist role`, and the final report lists it at the top.

## The Follow-ups list

Every follow-up appears in two places, with the same text:

1. The task file's `## Follow-ups` section (add the section above `## Plan` if an older task file lacks it). This is what spec-reviewer checks, and it survives the merge with the archived task.
2. The PR body's **Follow-ups** section, copied from it.

Each bullet: what was noticed, then `→` and exactly one of:

- `<path> § <section>`, optionally `(new)`, `(approved at plan)`, or `(proposed)`;
- `not tracked: <reason>`.

```
- 1.3c: a range like `#5-5` is a `bad_range`; the error copy should say why → docs/tasks/TASK-005-range-errors.md § Context
- Leading zeros aren't canonicalised (`#01` vs `#1`) → not tracked: done in this PR (plan revision)
- Candidate decision: suggestions use pg_trgm's 0.3 threshold → docs/review/owner-checklist.md § Approvals
```

## Reading and editing large docs

If a destination is listed in `largeFiles` (a long roadmap, a design export), never read it whole: use its hint, or Grep for the item's ID and Read with offset and limit around it, then Edit that range. With `"always": true`, don't read it at all; ask.

## Helpers

- **Next free ID** (decisions log, or IDs on any numbered list): `powershell -NoProfile -ExecutionPolicy Bypass -File .claude/scripts/next-id.ps1 -Path <log> -Prefix D-`. It reads the file in the working tree, on `origin/<base>`, and on every open PR's branch, so two branches never take the same ID. `-List -Pattern '\d+\.\d+[a-z]?' -Path <roadmap>` lists every roadmap ID in use across the same branches.
- **Follow-ups of merged PRs**: `.claude/scripts/list-follow-ups.ps1` (used by `/track-follow-ups`).

## Link commit

Headings written before the PR exists name the branch. Right after `gh pr create` returns the number, replace `(…, <branch>)` with `(…, PR #n)` in every file the Follow-ups list points to (Grep for the branch name), commit (`docs(<git-id>): link follow-ups to PR #n`, or `task <git-id>: link follow-ups to PR #n`), and push. If no PR is opened, the branch name stays; it still traces the note.

## Review rules (spec-reviewer enforces these)

- Every bullet in `## Follow-ups` ends in a destination or `not tracked: <reason>`.
- Every follow-up edit outside this task's files traces to one bullet, and every bullet with a path has its edit in the diff (except `(proposed)`).
- A follow-up edit never changes another task's acceptance criteria, Out of scope, or Plan, or any roadmap **Check:** line or checkbox. Ticks follow `.claude/skills/sync-roadmap/ticks.md` and are never follow-ups.
- New work is never `Ready`, and in roadmap mode gets no task file.
- A destination-6 edit or recorded `propose` decision is listed as approved (at plan, at close-out, or a ticked checklist item).
