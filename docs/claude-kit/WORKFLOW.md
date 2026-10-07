# Workflow: the method behind the kit

Why the kit is shaped the way it is, and how to decide how much autonomy to give it. Step-by-step usage is in `USER-GUIDE.md`.

## Principles

1. **The task file is the contract.** Claude plans, builds, and gets reviewed against its acceptance criteria. Vague ACs are the largest single source of rework.
2. **Your attention is the bottleneck, not dispatch.** Automation should move your effort to the two gates where it matters most: plan approval and PR review.
3. **Claude proves its work before you see it.** Hooks check every edit; test-runner, test-auditor and reviewers gate every task; CI gates every PR.
4. **Fresh context where independence matters.** Planning and implementing share one session. Review, verbose test runs, and browser checks go to subagents.
5. **Autonomy is earned per task type.** Small, pattern-following tasks go unattended; schema, auth and ETL never do.
6. **Decisions are written once.** `docs/decisions.md` keeps settled choices settled.

## Autonomy levels

| Level | Mechanism | Your gates | Use for |
|---|---|---|---|
| 1. Attended | `/next-task` or `/implement-task` in your session | Plan (live), PR | Default; all `attended` tasks |
| 2. Batch-planned | `/plan-batch` → approve → `dispatch-approved.ps1` → agent view | Plans (batched), PR | `unattended` tasks once metrics are on target |
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
| 8 | CI | "Works on my machine"; migrations on a clean DB; e2e smoke | Phase 7, every PR |
| 9 | Claude PR review (optional) | A second fresh-context review on GitHub | When the PR leaves draft |
| 10 | You | Product judgement, taste, the manual check | PR review |

For unattended work, layers 4, 7 and 8 are what make a PR you didn't watch trustworthy.

## Guardrails for unattended work

| Guardrail | How the kit enforces it |
|---|---|
| Never touch the base branch | `permissions.deny` on pushes to main/master, force-push, `gh pr merge`; GitHub ruleset as the backstop |
| No secrets or immutable files edited | `protectedPaths` + PreToolUse guard hook |
| Isolated workspaces | Background sessions move into `.claude/worktrees/<id>` before editing |
| Bounded effort | Round limits: verify 3, audit 2, review 2, CI 2; then Blocked with a written hypothesis |
| No silent spec changes | Claude proposes AC rewrites; only you apply them |
| Plans that match the code | `planned_at_commit` staleness check before unattended work starts |
| Review capacity | WIP limit (default 2) counts tasks in progress and in review |
| Quota awareness | Each background session draws on your quota independently; the WIP limit caps it |
| No prompts for routine commands | Allow-rules for verify, git and gh commands, added by `/customize-kit` |

## Model routing

| Work | Model |
|---|---|
| Discovery, architecture, `/new-task`, `/plan-batch`, per-task planning | Opus |
| Implementation of S/M pattern-following tasks | Sonnet (`model: sonnet`) |
| Schema, migrations, auth, ETL, concurrency | Opus throughout |
| spec-reviewer, schema-reviewer | Opus |
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
| Let Claude rewrite ACs to pass review | You rewrite ACs; Claude proposes |

## Retro (every ~10 tasks, about 20 minutes)

Regenerate the board, then ask Claude: "Analyze the metrics in `docs/tasks/INDEX.md` and the Review logs of the last 10 task files. Which leak is largest, and what single change to the kit, CLAUDE.md, or the AC rules would reduce it?" Apply one change at a time so you can see its effect.
