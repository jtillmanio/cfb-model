---
name: implement-task
description: Runs the full loop for one task file in docs/tasks/ — preflight, plan gate, implement, verify, test audit, review, PR, ready gates. Use when the user runs /implement-task, asks to implement or work on a specific TASK-### file, or when /next-task or the dispatcher hands over a task.
argument-hint: TASK-ID [--unattended]   e.g. TASK-014  or  TASK-014 --unattended
---

# Implement task: $ARGUMENTS

> **Doc roles:** names in **bold** such as **Architecture**, **Data model**, or **Decisions** are roles in the "Project docs" table in `CLAUDE.md`. Always read and write the path the table gives for a role, including a `§ section` if it names one. The path in parentheses is only the default, used when the table is missing. If a role maps to `—`, follow the fallback stated in the step, or ask. Refer to sections by name, never by number.

> **Project overrides:** read `.claude/kit.json` once at the start; its `workflow`, `verify`, `testAudit` and `ui` keys drive the steps below, and a missing key takes the default named in the step. Then read `.claude/project/implement-task.md` if it exists. It holds this project's instructions for this skill and wins where it conflicts with this file, except that it can't lower the floor: never push to or merge into the base branch, never rewrite acceptance criteria, never start a deploy, never skip the plan gate.

Parse `$ARGUMENTS`: the first token is the task ID; `--unattended` sets **unattended mode**.

| | Attended (default) | Unattended (`--unattended`, used by the dispatcher) |
|---|---|---|
| Plan gate | Stop and wait for approval, unless the plan is already approved and fresh | Plan must already be approved and fresh, otherwise stop |
| Questions | Ask in the conversation | Ask anyway: the session shows as Needs input in agent view, and the user answers there |
| Commit, push, PR | Ask once in Phase 6 before pushing | Do it: commit, push the task branch, open a draft PR |
| After the round limits | Stop and report | Mark the task Blocked, push, open a draft PR titled `[BLOCKED]`, report |

Each phase ends in a gate; never start a phase before the previous gate passes.

## Names, commits, and staging

- **Roadmap mode** is on when `workflow.roadmap` is set. The task's **roadmap ID** is the first match of `workflow.roadmap.idPattern` in its `title`, and its **Check** is the line starting with `workflow.roadmap.checkLabel` under that ID in `workflow.roadmap.path`. The roadmap outranks the task file: where they disagree, the task file is the bug; say so and ask.
- **Git ID**: the roadmap ID in roadmap mode, otherwise the task ID.
- **Branch**: `workflow.taskBranch` (default `task/{id}-{slug}`) with `{id}` = the git ID, lowercase, and `{slug}` = a short kebab-case slug of the title. `{type}` is the `workflow.branchPrefixes` entry, without its slash, that fits the task, using the meanings in `.claude/rules/git.md` (e.g. `feat` for a feature, `fix` for a bug); if none clearly fits, ask. With conventional commits, use the same word as the commit type when it is one.
- **Commit subjects** follow `workflow.commitFormat` (default `conventional`):

  | Commit | `conventional` | `area` |
  |---|---|---|
  | Checkpoint | `<type>(<git-id>): <summary>` | `task <git-id>: <summary>` |
  | Close-out | `docs(<git-id>): close out` | `task <git-id>: close out` |
  | Accept | `chore(<git-id>): accept` | `task <git-id>: accept` |
  | Blocked | `chore(<git-id>): blocked` | `task <git-id>: record blocker` |

  Subjects are imperative, at most 72 characters, no trailing period. The body says why and cites IDs (task, decision, review finding). End with the session's attribution trailer.
- **Staging** follows `workflow.staging` (default `by-path`). By path: run `git status --porcelain`, stage only the files this task changed with `git add <file> …`, then read `git diff --staged` before committing. Leave every other change alone; it is the owner's. `all` restores `git add -A`.

## Phase 0: Preflight

1. Find `docs/tasks/<ID>*.md`. If there are zero or several matches, stop and list what you found.
2. If `status` is `Done`, stop. If any `depends_on` task isn't `Done` in its task file, list the blockers and stop.
3. Check every acceptance criterion is checkable (an observable result plus an expected value). In roadmap mode, also read the roadmap entry and its Check (use the `largeFiles` hint if the roadmap is listed there). If any AC isn't checkable, list proposed rewrites and stop. Never rewrite ACs yourself.
4. **Workspace**:
   - Run `git status --porcelain`. If there are unrelated uncommitted changes, stop and ask. The test audit needs a tree with only this task's work in it.
   - Create the branch (see Names) if you are on `workflow.baseBranch`. If you are in a worktree Claude Code created (under `.claude/worktrees/`) on an auto-named branch, rename that branch with `git branch -m`.
   - If you are in a worktree: run each `workflow.worktreeSetup` command, and copy each `workflow.worktreeCopyFiles` path from the main checkout (the first path in `git worktree list --porcelain`) if it isn't already present. Report failures and stop.
5. **Plan freshness**: if `plan_status: approved`, compare against `planned_at_commit`:
   `git diff --stat <planned_at_commit>..HEAD -- <files listed in the Plan>`
   If any planned file changed since the plan, the plan is **stale**. Attended: tell the user and re-plan in Phase 1. Unattended: stop and report `plan stale` with the changed files.
6. Unattended only: if `plan_status` isn't `approved`, stop and report.
7. Set `status: In progress` in the task file. Do not edit `docs/tasks/INDEX.md`; it is generated.

## Phase 1: Plan (skip if the plan is approved and fresh)

1. Read the CLAUDE.md hard rules and "Which document wins", the **Decisions** log, and every doc and design file the task's Context section cites. Read the files themselves, not summaries. A UI task also reads the **UX floor** if the project has one.
2. Explore the code. Delegate broad searches to Explore.
3. Draft the plan:
   - **Steps**: numbered, each one verifiable on its own
   - **Files**: each file to create or change, with a one-line reason; flag any that aren't in "Files likely touched". A UI task that changes a screen drawn in a `ui.redrawFiles` file lists that file too: its frame is redrawn in the same PR.
   - **Test strategy**: for each AC, the test file and test name that will prove it, or the manual step if it can't be automated
   - **Risks / open questions**
   - **Size check**: more than 8 files, or schema and UI together. With `workflow.splitPolicy` `split` (default), propose a split instead of a plan. With `never-split`, keep the task whole, set `autonomy: attended`, and say in the plan why it is large.
4. **GATE**: present the plan in under 30 lines and stop for approval.
5. After approval, write the plan into `## Plan`, set `plan_status: approved` and `planned_at_commit: <git rev-parse --short HEAD>`.

## Phase 2: Implement

1. For each automated AC, write or extend the test first and confirm it fails for the expected reason.
2. Implement in plan order and stay inside the plan. If you must deviate (new file, different approach, newly discovered requirement), explain it in 2–3 lines and ask. Update `## Plan` once agreed and count it under "Plan revisions after approval".
3. Fix post-edit hook failures before moving on, except while a multi-file change is half-done.
4. If the spec is wrong or contradicts existing code, ask. Never pick an interpretation silently.

## Phase 3: Verify (max 3 rounds)

1. Delegate to **test-runner**. Fix any failures here and re-run.
2. **GATE**: PASS. After 3 failed rounds, go to the blocked path (see the end of this file).
3. **Checkpoint commit** on the task branch (see Names: staging and subject). The test audit needs a clean tree; more commits will follow.

## Phase 4: Test audit (max 2 rounds)

1. Delegate to **test-auditor** with the task file path and base ref.
2. Strengthen any UNPROVEN or NON-DISCRIMINATING tests, re-run test-runner, commit, and re-audit.
3. **GATE**: PASS. If it returns NOT RUN because of restoration, stop everything and report it; do not continue on a possibly altered tree.

## Phase 5: Review (max 2 rounds)

Delegate the reviewers that apply, in parallel:

| Reviewer | When |
|---|---|
| **spec-reviewer** | Always. Give it the task file and base ref |
| **schema-reviewer** | The diff touches migrations, schema, views, queries, or seed/ETL code |
| **ui-verifier** | The task has `ui: true` or changes UI files, and `ui.startCommand` is configured |

For ui-verifier:
- Port = `ui.portBase` + (task number mod 100).
- Substitute `{port}` in `ui.startCommand` and `ui.baseUrl`.
- Start the dev server as a background command, wait until the URL responds, pass the resolved URL to the agent, and stop the server afterwards.

Then:
- Fix every FAIL, UNTESTED, PLAN GAP, rule violation, and unjustified SCOPE CREEP.
- For a SPEC GAP, ask the user.
- If code changed, re-run test-runner and commit before the next round.

**GATE**: every reviewer that ran returns APPROVE. If an agent is unavailable, run its checklist yourself and say the review was not independent.

## Phase 6: Close out and open the PR

1. Fill in the task file:
   - `## Review log`: one line per round, e.g. `Verify R1 FAIL(2) → R2 PASS | Audit R1 PASS | Spec R1 CHANGES (AC-3 UNTESTED) → R2 APPROVE | UI R1 PASS`
   - `## Metrics`
   - Tick the AC checkboxes that passed
   - `status: Review`
2. Roadmap mode: tick the task's checkbox in the roadmap file in this same PR. Never edit `workflow.statusDoc`; it is regenerated from the roadmap, not from task files.
3. Lasting decisions (new dependency, pattern, schema convention, rejected approach) follow `workflow.decisions`:
   - `append` (default): add a row to the **Decisions** log, using the ID prefix the table gives.
   - `propose`: don't touch the log. List each one under **Follow-ups** in the PR body as "Candidate decision: …" for the owner to record.
4. Commit the close-out (see Names).
5. If `workflow.openPullRequests` is true:
   - Attended: ask once, "Push and open a draft PR?"
   - Unattended: proceed.
   - Push with `git push -u origin <task-branch>` (never the base branch, never force).
   - Create the PR with `gh pr create --draft --base <baseBranch> --title "<title>" --body-file <tmp>`. The title is a commit subject in `workflow.commitFormat` (e.g. `feat(TASK-014): show run progress`, or `task 1.3: parse bulk-entry labels`), because the squash merge keeps it. Put the temp file in the session temp directory, not the repo.
   - Build the body from `.github/pull_request_template.md`:
     - **What**: the change in a few bullets, with the task file path.
     - **Why**: the problem, with task, roadmap, decision, and review-finding IDs.
     - **Acceptance criteria**: in roadmap mode the roadmap Check first, verbatim; then the task file's ACs, ticked when verified.
     - **How it was verified**: a `Check | Where | Result` table. One row each for test-runner, test-auditor, and every reviewer that ran, then one row per ready gate (Phase 7), owner gates marked `owner`. Say which suites ran only in CI, and name anything that can only be checked after merge, why, and the exact check to run then. Screenshot names from ui-verifier.
     - **Manual verification**: the task's manual steps, each with its expected result.
     - **Follow-ups**: work noticed and deliberately left out, as candidate tasks; candidate decisions when `workflow.decisions` is `propose`.
     - **Reviewer checklist**: as in the template.
6. If `workflow.openPullRequests` is false, report the proposed commit history and stop.

## Phase 7: Ready gates (only if a PR was opened and `workflow.waitForCi` is true)

`workflow.readyGates` lists, in order, what must pass on the branch before the PR is marked ready. Default: `["verify.full", "ci"]`. Each entry is a built-in name or an object `{ name, check, by, when, failureLog, ownerFix }`.

1. **Which gates apply.** A gate's `when` is `always` (default), `ui` (the task has `ui: true` or changes UI files), or a list of path globs (applies when the diff touches a matching path).
2. **Check each Claude gate in order** (`by: claude`, and both built-ins):
   - `verify.full`: test-runner PASS on the branch head. If code changed after the last PASS, re-run test-runner.
   - `ci`: `gh pr checks <number> --watch --interval 30`. The required job is `workflow.ciJobName` (default `verify`).
   - An object gate: do what its `check` says and judge the result.
3. **When a Claude gate fails**, fix it on the branch, commit, push, and check again. Allow at most `workflow.maxCiFixRounds` rounds across all gates.
   - Read the failure where it lives: `gh run view <run-id> --log-failed` for an Actions run; the gate's `failureLog` when it names another place (e.g. a hosting provider's deployment log, which `gh run view` can't see).
   - If the fix needs something only the owner can do (the gate's `ownerFix` describes it, or the log shows it), stop. Don't loop. Report the owner action and leave the PR in draft.
4. **Owner gates** (`by: owner`) are never checked by Claude. List them in the PR's verification table as `owner` and in the final report.
5. When every applicable Claude gate has passed, run `gh pr ready <number>`. This also triggers Claude's PR review, if that workflow is installed.

If `workflow.waitForCi` is false, leave the PR in draft and list every gate in the final report.

## Final report (under 25 lines)

- PR link, or branch name if no PR
- Files changed, one line each
- Reviewer verdicts, ready-gate results, and metrics
- Manual verification steps with expected results
- The owner's gates still to check, and the owner's next steps (from the **Owner checklist** or **Owner runbook**, if the task touches them). Never run runbook commands yourself.
- Follow-up work you noticed, written as candidate tasks. Do not implement them.
- In unattended mode: `Reply "accepted" after your manual check to set status: Done and push.`
- Last line, if `workflow.afterMerge` is set: that text, verbatim.

If the user later replies "accepted" (in the session or via agent view), set `status: Done` in the task file, commit it (Accept subject; stage the task file only), and push. Never merge. Done means merged and accepted, not deployed.

## Blocked path

Use this when a round limit is hit, the plan is stale (unattended), or a check can't be resolved.

1. Set `status: Blocked` and add a `## Blocked` section to the task file: what failed, what you tried, your best hypothesis, and what decision or input is needed.
2. Commit all of this task's work (Blocked subject; stage by path as above).
3. Unattended: push the branch and open a draft PR titled `[BLOCKED] <title>` so the work isn't lost.
4. Report the same summary.
