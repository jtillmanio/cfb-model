# Claude Code starter kit v2

A stack-agnostic `.claude/` setup that turns task files into reviewed, CI-green pull requests, either one at a time with you in the loop, or batch-planned and run unattended in parallel background sessions.

| Read | For |
|---|---|
| `KICKOFF.md` | Starting from scratch: idea → scope → design → architecture → skeleton → first tasks |
| `USER-GUIDE.md` | Install, setup, day-to-day use, reference, troubleshooting |
| `WORKFLOW.md` | The method: autonomy levels, review layers, guardrails, metrics |
| `CHANGELOG.md` | What changed since v1 and how to upgrade |

## Quick start

New project, or only a brainstorm or design so far? Follow `KICKOFF.md`. Existing codebase:

1. Install: copy the kit into your project root without overwriting (USER-GUIDE §3).
2. Restart Claude Code, `/model opus`, run `/customize-kit`.
3. Protect your base branch and, optionally, run `/install-github-app` (USER-GUIDE §5).
4. `/milestones`, then `/new-task docs/tasklist.md M1`; review the task files and set them to `Ready`.
5. `/next-task`.

## What's in the kit

| Path | What it is |
|---|---|
| `CLAUDE.md` | Project memory template: commands, hard rules, workflow and git rules |
| `.claude/kit.json` | One config for verify commands, protected paths, workflow, test audit, UI checks |
| `.claude/settings.json` | Hook registration and deny rules (no pushes to main, no force-push, no merges) |
| `.claude/.gitignore` | Keeps worktrees, state, tmp, and local settings out of git |
| `.claude/hooks/post-edit-verify.ps1` | Runs fast checks after each edit; failures go straight back to Claude |
| `.claude/hooks/guard-protected-paths.ps1` | Blocks edits to secrets, applied migrations, generated files |
| `.claude/agents/test-runner.md` | Runs the full suite; returns failures only (Haiku) |
| `.claude/agents/test-auditor.md` | Proves new tests fail without the change (Sonnet) |
| `.claude/agents/spec-reviewer.md` | Diff vs. ACs, plan, scope, hard rules, decisions (Opus, read-only) |
| `.claude/agents/schema-reviewer.md` | Migrations, constraints, data safety (Opus, read-only) |
| `.claude/agents/ui-verifier.md` | Drives a browser through UI ACs at phone and desktop widths (Sonnet + Playwright) |
| `.claude/skills/product-brief/` | `/product-brief`: brainstorm notes → brief, feature list, screen inventory, Claude Design prompt |
| `.claude/skills/architecture/` | `/architecture`: decision options → architecture doc + seeded decisions |
| `.claude/skills/skeleton/` | `/skeleton`: walking skeleton with every script, tests, and CI working |
| `.claude/skills/milestones/` | `/milestones`: demoable milestones and task stubs with a coverage check |
| `.claude/skills/customize-kit/` | `/customize-kit`: tailor everything to the project |
| `.claude/skills/new-task/` | `/new-task`: task files with checkable ACs; bulk-convert a task list |
| `.claude/skills/next-task/` | `/next-task`: pick the best Ready task and run it attended |
| `.claude/skills/implement-task/` | `/implement-task`: the full loop, attended or `--unattended` |
| `.claude/skills/plan-batch/` | `/plan-batch`: plan several tasks for one approval sitting |
| `.claude/scripts/build-index.ps1` | Generates the local task board with metrics and warnings |
| `.claude/scripts/dispatch-approved.ps1` | Starts background sessions for approved unattended tasks, within the WIP limit |
| `.claude/scripts/lib-tasks.ps1` | Shared task-file parser |
| `docs/templates/` | Templates for the brief, feature list, architecture doc, and task list |
| `docs/tasks/_TEMPLATE.md` | Task file template |
| `docs/tasks/.gitignore` | Keeps the generated `INDEX.md` out of git |
| `docs/decisions.md` | Decisions log template |
| `.github/workflows/ci.yml` | CI gate template (`verify` job), filled by `/customize-kit` |
| `.github/workflows/claude-pr-review.yml` | Optional: Claude reviews PRs when they leave draft |
| `.github/workflows/claude.yml` | Optional: `@claude` in issues and PR comments |
| `.github/pull_request_template.md` | PR body with AC checklist, evidence table, manual steps |

## Requirements

Windows with PowerShell 5.1+ and Git for Windows; Claude Code v2.1.139+; GitHub CLI; Node.js 18+ for the browser checks; a Claude Pro, Max, Team, or Enterprise plan.
