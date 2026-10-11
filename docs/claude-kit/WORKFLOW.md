# Workflow: the method behind the kit

Why the kit is shaped the way it is, and how to decide how much autonomy to give it. Step-by-step usage is in `USER-GUIDE.md`.

## Principles

1. **The task file is the contract.** Claude plans, builds, and gets reviewed against its acceptance criteria. Vague ACs are the largest single source of rework.
2. **Your attention is the bottleneck, not dispatch.** Automation should move your effort to the two gates where it matters most: plan approval and PR review.
3. **Claude proves its work before you see it.** Hooks check every edit; test-runner, test-auditor and reviewers gate every task; CI gates every PR.
4. **Fresh context where independence matters.** Planning and implementing share one session. Review, verbose test runs, and browser checks go to subagents.
5. **Autonomy is earned per task type.** Small, pattern-following tasks go unattended; schema, auth and ETL never do.
6. **Decisions are written once.** The decisions log (the **Decisions** role in `CLAUDE.md`) keeps settled choices settled.
7. **Merged is not live.** Done means merged and accepted. If the project deploys separately, that step is the owner's, and Claude never starts it.
8. **The project changes the kit through switches, not patches.** `workflow.*` keys in `kit.json` and `.claude/project/<name>.md` files survive every upgrade; edits to the kit's own skills don't.

## Autonomy levels

| Level | Mechanism | Your gates | Use for |
|---|---|---|---|
| 1. Attended | `/next-task` or `/implement-task` in your session | Plan (live), PR | Default; all `attended` tasks |
| 2. Batch-planned | `/plan-batch` → approve → plans PR → `dispatch-approved.ps1` → agent view | Plans (batched), PR | `unattended` tasks once metrics are on target |
| 3. Remote | `@claude` on GitHub (`claude.yml`) | PR | Small unattended fixes sent from your phone |
| 4. Continuous loop | Not included | None | Not recommended for a solo project; output outpaces review |

### When to move a task type up a level

Check the metrics in `INDEX.md` over your last ~10 tasks of that type:

| Metric | Target before going to Level 2 |
|---|---|
| First-pass AC FAILs | 0 on ≥ 80% of tasks |
| Review rounds | 1 on ≥ 70% of tasks |
| Plan revisions after approval | 0 on ≥ 90% of tasks |
| Verify rounds | ≤ 2 |

These are starting targets. Adjust them once you have your own baseline. If a task type regresses after promotion, move it back to Level 1.

## The review layers

| # | Layer | Catches | Where |
|---|---|---|---|
| 1 | Checkable ACs | Building the wrong thing | `/new-task`, preflight |
| 2 | Post-edit hook | Type/lint errors within seconds | `verify.fast` |
| 3 | Tests first, per AC + test-runner | Logic errors | Phases 2–3 |
| 4 | test-auditor | Tests that pass no matter what | Phase 4 |
| 5 | spec-reviewer | Spec drift, plan gaps, scope creep, rule violations | Phase 5 |
| 6 | schema-reviewer | Data loss, integrity, migration safety | Phase 5 (data changes) |
| 7 | ui-verifier | UI that compiles but doesn't work; design drift; console errors | Phase 5 (UI changes) |
| 8 | Ready gates | "Works on my machine": `verify.full` on the branch head, CI (migrations on a clean DB, e2e smoke), plus the project's own gates (preview deployed, performance budget, a workflow run on the branch) | Phase 7, every PR |
| 9 | Claude PR review (optional) | A second fresh-context review on GitHub | When the PR leaves draft |
| 10 | You | Product judgement, taste, the manual check | PR review |

For unattended work, layers 4, 7 and 8 are what make a PR you didn't watch trustworthy.

## Ready gates: test on the branch, never on the base

A PR is ready only when everything that can prove the change has run against the branch and passed. "It will show up on main" is not a test: a failure found after merge means reverting the base branch.

`workflow.readyGates` lists those checks in order. The default is `verify.full` locally, then CI. A project adds its own, each with how to check it and who can:

| Gate (examples) | Checked by | Notes |
|---|---|---|
| `verify.full` on the branch head | Claude | Built in; test-runner re-runs it if code changed after the last pass |
| CI (`workflow.ciJobName`) | Claude | Built in; skipped when `waitForCi` is false |
| Preview deployed | Claude | Its failure log is the hosting provider's, not an Actions run: set `failureLog` |
| Performance budget green on the preview | Claude | `docs/templates/github/perf-budget.yml` |
| Changed workflow run with `gh workflow run <file> --ref <branch>` | Claude | `when: [".github/workflows/*"]` |
| UI walked on the preview at phone width | Owner | `when: "ui"` |

Claude marks the PR ready only when every applicable gate it can check has passed; owner gates appear in the PR's "How it was verified" table and in the final report. When fixing a gate needs something only the owner can do (`ownerFix`, e.g. resetting a preview's database), Claude stops and says so instead of looping. Something that truly can't run before merge goes in the PR with the reason and the exact check to run straight after.

## Done vs. deployed

| State | Means | Who |
|---|---|---|
| Review | PR open and ready; every Claude gate passed | Claude |
| Done | You did the owner gates and the manual check and said "accepted"; then you merge | You |
| Live | Production runs it. Same as Done only when merging deploys | You, through the **Deploy** role (e.g. a hand-run release); Claude never starts it |

`workflow.afterMerge` is the line every final report ends with when merging and going live differ, e.g. "After merge, run Release to put it live." `docs/templates/github/release.yml` is a starting point for a release that refuses unless CI passed on the exact commit, snapshots the database, migrates, re-applies anything derived, promotes, and smoke-tests a health route.

## Level 2 procedure: plans reach the base branch through a PR

The dispatcher only sees approved plans committed on the base branch, and nothing is committed on the base branch directly. So:

1. On an up-to-date base branch with a clean tree, run `/plan-batch`. It edits task files only and commits nothing, so each `planned_at_commit` is a base-branch commit that still exists after a squash merge.
2. Review and approve the plans (`plan_status: approved`).
3. Move them to a `docs/plans-<date>` branch (the uncommitted plans come along), commit them by path, push, open a PR.
4. You merge it.
5. `git switch <base>`, `git pull --ff-only`, `dispatch-approved.ps1 -DryRun`, then dispatch.

The planned files' staleness check still works: the plans PR touches only task files, so `git diff <planned_at_commit>..HEAD -- <planned files>` stays empty unless the code really moved.

## Guardrails for unattended work

| Guardrail | How the kit enforces it |
|---|---|
| Never touch the base branch | `permissions.deny` on pushes to main/master, force-push, `gh pr merge`, for both the Bash and PowerShell tools; `.claude/rules/git.md`; GitHub ruleset as the backstop where the plan allows one |
| Never sweep in the owner's work | Staging by path (`workflow.staging`); `git add -A`, `git add .` and `git commit -a` denied |
| Never deploy or touch production | Deny rules for the project's deploy, release, and production-data commands; `Read(...)` denies for production env files; tests read the test database only |
| No secrets or source files edited | `protectedPaths` + PreToolUse guard hook |
| No context blown on one file | `largeFiles` + the large-read guard hook |
| Isolated workspaces | Background sessions move into `.claude/worktrees/<id>` before editing |
| Bounded effort | Round limits: verify 3, audit 2, review 2, CI 2; then Blocked with a written hypothesis |
| No silent spec changes | Claude proposes AC rewrites; only you apply them |
| Plans that match the code | `planned_at_commit` staleness check before unattended work starts |
| Review capacity | WIP limit (default 2) counts tasks in progress and in review; 1 when worktrees share a test resource |
| Quota awareness | Each background session draws on your quota independently; the WIP limit caps it |
| No prompts for routine commands | Allow-rules for verify, git and gh commands, added by `/customize-kit` |

## Model routing

| Work | Model |
|---|---|
| Discovery, architecture, `/new-task`, `/plan-batch`, per-task planning | Opus |
| Implementation of S/M pattern-following tasks | Sonnet (`model: sonnet`) |
| Schema, migrations, auth, ETL, concurrency | Opus throughout |
| spec-reviewer, schema-reviewer | Opus (or Sonnet with `effort: high`, set per agent) |
| test-auditor, ui-verifier | Sonnet |
| test-runner | Haiku |

## Subagents vs. sessions vs. worktrees

| Need | Use |
|---|---|
| Plan and implement one task | One main session (shared context) |
| Independent review or verbose output | Subagent (fresh context; returns a summary) |
| Several tasks at once | Background sessions via the dispatcher; each gets its own worktree |
| A quick side question | `/btw` |

## Context hygiene

- `/clear` between attended tasks. Background sessions start fresh by design.
- The plan lives in the task file, so model switches, compaction, and session restarts lose nothing.
- Point Claude at files, not memories: "match `design/screens.html` § Run Detail."
- When you correct the same mistake twice, add a line to CLAUDE.md "Gotchas". Keep CLAUDE.md under ~100 lines.

## Anti-patterns

| Don't | Do instead |
|---|---|
| Dispatch tasks whose plans you skimmed | Batch-plan when you can give it focused time |
| Raise the WIP limit to "go faster" | Merge faster; open PRs are inventory |
| Let schema tasks run unattended or in parallel | Keep them attended and serial |
| Accept a PR because CI is green | Do the manual steps; CI can't judge the product |
| Edit `INDEX.md` | Edit task files; regenerate |
| Patch a kit skill to change its behaviour | Set a `workflow` switch, or write `.claude/project/<skill>.md` |
| Copy a number from a mockup into an AC | Assert a relationship, or build a fixture |
| Commit approved plans on the base branch | Plans PR on a `docs/plans-<date>` branch |
| Let Claude rewrite ACs to pass review | You rewrite ACs; Claude proposes |

## Retro (every ~10 tasks, about 20 minutes)

Regenerate the board, then ask Claude: "Analyze the metrics in `docs/tasks/INDEX.md` and the Review logs of the last 10 task files (most are in `docs/tasks/archive/`). Which leak is largest, and what single change to a `workflow` switch, a `.claude/project/` file, CLAUDE.md, or the AC rules would reduce it?" Apply one change at a time so you can see its effect.

If the project runs independent review rounds (the **Review findings** role: a protocol plus a findings ledger, from `docs/templates/review-*.md`), include the ledger: open findings whose "proceed without fix?" names a task you've reached are due now. Commits and PRs cite finding IDs, so the ledger's status can be checked against the history.
