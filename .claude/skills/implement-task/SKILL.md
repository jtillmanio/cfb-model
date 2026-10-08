---
name: implement-task
description: Runs the full loop for one task file in docs/tasks/ — preflight, plan gate, implement, verify, test audit, review, PR, CI. Use when the user runs /implement-task, asks to implement or work on a specific TASK-### file, or when /next-task or the dispatcher hands over a task.
argument-hint: TASK-ID [--unattended]   e.g. TASK-014  or  TASK-014 --unattended
---

# Implement task: $ARGUMENTS

> **Doc roles:** names in **bold** such as **Architecture**, **Data model**, or **Design tokens** are roles in the "Project docs" table in `CLAUDE.md`. Always read and write the path the table gives for a role, including a `§ section` if it names one. The path in parentheses is only the default, used when the table is missing. If a role maps to `—`, follow the fallback stated in the step, or ask. Refer to sections by name, never by number.

Parse `$ARGUMENTS`: the first token is the task ID; `--unattended` sets **unattended mode**.

| | Attended (default) | Unattended (`--unattended`, used by the dispatcher) |
|---|---|---|
| Plan gate | Stop and wait for approval, unless the plan is already approved and fresh | Plan must already be approved and fresh, otherwise stop |
| Questions | Ask in the conversation | Ask anyway: the session shows as Needs input in agent view, and the user answers there |
| Commit, push, PR | Ask once in Phase 6 before pushing | Do it: commit, push the task branch, open a draft PR |
| After the round limits | Stop and report | Mark the task Blocked, push, open a draft PR titled `[BLOCKED]`, report |

Read `.claude/kit.json` once at the start. `workflow`, `verify`, `testAudit` and `ui` drive the steps below. Each phase ends in a gate; never start a phase before the previous gate passes.

## Phase 0: Preflight

1. Find `docs/tasks/<ID>*.md`. If there are zero or several matches, stop and list what you found.
2. If `status` is `Done`, stop. If any `depends_on` task isn't `Done` in its task file, list the blockers and stop.
3. Check every acceptance criterion is checkable (an observable result plus an expected value). If any isn't, list proposed rewrites and stop. Never rewrite ACs yourself.
4. **Workspace**:
   - Run `git status --porcelain`. If there are unrelated uncommitted changes, stop and ask.
   - Branch name is `task/<id-lowercase>-<short-slug>`. If on `workflow.baseBranch`, create it. If you are in a worktree Claude Code created (under `.claude/worktrees/`) on an auto-named branch, rename that branch with `git branch -m`.
   - If you are in a worktree: run each `workflow.worktreeSetup` command, and copy each `workflow.worktreeCopyFiles` path from the main checkout (the first path in `git worktree list --porcelain`) if it isn't already present. Report failures and stop.
5. **Plan freshness**: if `plan_status: approved`, compare against `planned_at_commit`:
   `git diff --stat <planned_at_commit>..HEAD -- <files listed in the Plan>`
   If any planned file changed since the plan, the plan is **stale**. Attended: tell the user and re-plan in Phase 1. Unattended: stop and report `plan stale` with the changed files.
6. Unattended only: if `plan_status` isn't `approved`, stop and report.
7. Set `status: In progress` in the task file. Do not edit `docs/tasks/INDEX.md`; it is generated.

## Phase 1: Plan (skip if the plan is approved and fresh)

1. Read the CLAUDE.md hard rules, `docs/decisions.md`, and every doc and design file the task's Context section cites. Read the files themselves, not summaries.
2. Explore the code. Delegate broad searches to Explore.
3. Draft the plan:
   - **Steps**: numbered, each one verifiable on its own
   - **Files**: each file to create or change, with a one-line reason; flag any that aren't in "Files likely touched"
   - **Test strategy**: for each AC, the test file and test name that will prove it, or the manual step if it can't be automated
   - **Risks / open questions**
   - **Size check**: more than 8 files, or schema and UI together, means propose a split instead of a plan
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
3. **Checkpoint commit** on the task branch: `git add -A` and `git commit -m "<type>(<id>): <summary>"`. The test audit needs a clean tree; more commits will follow.

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
2. Append lasting decisions (new dependency, pattern, schema convention, rejected approach) to `docs/decisions.md`.
3. Commit (`docs(<id>): close out`).
4. If `workflow.openPullRequests` is true:
   - Attended: ask once, "Push and open a draft PR?"
   - Unattended: proceed.
   - Push with `git push -u origin <task-branch>` (never the base branch, never force).
   - Create the PR with `gh pr create --draft --base <baseBranch> --title "<id>: <title>" --body-file <tmp>`. Build the body from `.github/pull_request_template.md`, filled in with the AC checklist, the reviewer verdicts, screenshot names, and the manual steps with expected results. Put the temp file in the session temp directory, not the repo.
5. If `workflow.openPullRequests` is false, report the proposed commit history and stop.

## Phase 7: CI (only if a PR was opened and `workflow.waitForCi` is true)

1. Run `gh pr checks <number> --watch --interval 30`.
2. If checks fail, read the failing job logs (`gh run view <run-id> --log-failed`), fix, commit, push, and watch again. Allow at most `workflow.maxCiFixRounds` rounds.
3. When green, run `gh pr ready <number>` to mark it ready for review. This also triggers Claude's PR review, if that workflow is installed.

## Final report (under 25 lines)

- PR link, or branch name if no PR
- Files changed, one line each
- Reviewer verdicts and metrics
- Manual verification steps with expected results
- Follow-up work you noticed, written as candidate tasks. Do not implement them.
- In unattended mode, end with: `Reply "accepted" after your manual check to set status: Done and push.`

If the user later replies "accepted" (in the session or via agent view), set `status: Done` in the task file, commit `chore(<id>): accept`, and push. Never merge.

## Blocked path

Use this when a round limit is hit, the plan is stale (unattended), or a check can't be resolved.

1. Set `status: Blocked` and add a `## Blocked` section to the task file: what failed, what you tried, your best hypothesis, and what decision or input is needed.
2. Commit all work.
3. Unattended: push the branch and open a draft PR titled `[BLOCKED] <id>: <title>` so the work isn't lost.
4. Report the same summary.
