# Claude Code starter kit v2

A stack-agnostic `.claude/` setup that turns task files into reviewed, CI-green pull requests, either one at a time with you in the loop, or batch-planned and run unattended in parallel background sessions.

| Read | For |
|---|---|
| `KICKOFF.md` | Starting from scratch: idea → scope → design → architecture → skeleton → first tasks |
| `ADOPTING.md` | Existing projects: docs, design, repo, CI, DB, or code already in place |
| `USER-GUIDE.md` | Install, setup, day-to-day use, reference, troubleshooting |
| `WORKFLOW.md` | The method: autonomy levels, review layers, guardrails, metrics |
| `UPGRADING.md` | Upgrading a project from an earlier 2.x (2.5 → 2.6, 2.4 → 2.5, 2.3 → 2.4) |
| `CHANGELOG.md` | What changed in each version |

## Quick start

New project, or only a brainstorm so far? Follow `KICKOFF.md`. Existing docs, design, or code? Follow `ADOPTING.md` (`/adopt` does the mapping). Quick version for an existing codebase:

1. Install: with the kit at `C:\Development\tools\claude-code-starter-kit\` (USER-GUIDE §3.1), run `powershell -NoProfile -ExecutionPolicy Bypass -File C:\Development\tools\claude-code-starter-kit\install-kit.ps1` from your project root.
2. Restart Claude Code, `/model opus`, run `/customize-kit`.
3. Protect your base branch and, optionally, run `/install-github-app` (USER-GUIDE §5).
4. `/milestones`, then `/new-task docs/tasklist.md M1`; review the task files and set them to `Ready`.
5. `/next-task`.

## How a project changes the kit's behaviour

Without editing a single kit file, so `install-kit.ps1 -Upgrade` never undoes it:

| To change | Use |
|---|---|
| Commands, protected files, large files, viewports, sign-in | `.claude/kit.json` |
| Workflow behaviour: staging, commit format, branch prefixes, ready gates, decisions, task splitting, roadmap mode, after-merge line | `workflow.*` switches in `.claude/kit.json` |
| Anything a switch can't express, for one skill or agent | `.claude/project/<skill-or-agent-name>.md` (you write it; the kit never ships one) |
| Rules for every session | `CLAUDE.md`, and `.claude/rules/*.md` (path-scoped with `paths:` frontmatter) |
| Permissions | `.claude/settings.json` |

## What's in the kit

| Path | What it is |
|---|---|
| `install-kit.ps1` | Installs or upgrades the kit into a project; never overwrites your files (kit lives at `C:\Development\tools\claude-code-starter-kit\`) |
| `VERSION` | Kit version; recorded in each project's `.claude/kit-version` |
| `CLAUDE.md` | Project memory template: commands, project docs, which document wins, hard rules, workflow, stop-and-ask list |
| `.claude/kit.json` | One config for verify commands, protected paths, large files, workflow switches, test audit, UI checks |
| `.claude/settings.json` | Hook registration and deny rules (no pushes to the base branch, no force-push, no merges, no `git add -A`, no `gh repo delete`), for both the Bash and PowerShell tools |
| `.claude/rules/git.md` | Branches, staging, commit messages, testing on the branch, PRs, merging; loads in every session |
| `.claude/.gitignore` | Keeps worktrees, state, tmp, and local settings out of git |
| `.claude/hooks/post-edit-verify.ps1` | Runs the fast checks that apply to an edited file; failures go straight back to Claude |
| `.claude/hooks/guard-protected-paths.ps1` | Blocks edits to secrets, design sources, generated files |
| `.claude/hooks/guard-large-reads.ps1` | Blocks whole-file reads of files listed in `largeFiles`, with a hint for reading one part |
| `.claude/hooks/guard-destructive.ps1` | Reads every Bash/PowerShell command and denies deletes outside the project, of the project, its `.git` or a worktree, disk tools, and repo deletion; asks before deleting tracked or uncommitted work |
| `.claude/agents/test-runner.md` | Runs the full suite; returns failures only (Haiku) |
| `.claude/agents/test-auditor.md` | Proves new tests fail without the change, with one or several test runners (Sonnet) |
| `.claude/agents/spec-reviewer.md` | Diff vs. ACs (and the roadmap check), plan, scope, hard rules, decisions, UX floor (Opus, read-only) |
| `.claude/agents/schema-reviewer.md` | Migrations, constraints, data safety, test isolation (Opus, read-only) |
| `.claude/agents/ui-verifier.md` | Drives a browser through UI ACs at each viewport, signing in first if needed (Sonnet + Playwright) |
| `.claude/skills/adopt/` | `/adopt`: map an existing project's docs and design to kit roles; gap report |
| `.claude/skills/product-brief/` | `/product-brief`: brainstorm notes → brief, feature list, screen inventory, Claude Design prompt |
| `.claude/skills/architecture/` | `/architecture`: decision options → architecture doc + seeded decisions |
| `.claude/skills/skeleton/` | `/skeleton`: walking skeleton with every script, tests, test-database guard, migration check, and CI working |
| `.claude/skills/milestones/` | `/milestones`: demoable milestones and task stubs, or `--coverage` of an existing roadmap |
| `.claude/skills/customize-kit/` | `/customize-kit`: tailor everything to the project; upgrade pass for 2.3.x, 2.4.x, 2.5.x, and 2.6.x |
| `.claude/skills/new-task/` | `/new-task`: task files with checkable ACs; bulk-convert a task list or a roadmap sitting |
| `.claude/skills/next-task/` | `/next-task`: pick the best Ready task and run it attended |
| `.claude/skills/implement-task/` | `/implement-task`: the full loop, attended or `--unattended` |
| `.claude/skills/plan-batch/` | `/plan-batch`: plan several tasks for one approval sitting |
| `.claude/skills/track-follow-ups/` | `/track-follow-ups`: backfill follow-ups merged PRs left untracked; `classify.md` is where every skill places follow-ups |
| `.claude/scripts/build-index.ps1` | Generates the local task board with metrics and warnings |
| `.claude/scripts/dispatch-approved.ps1` | Starts background sessions for approved unattended tasks, within the WIP limit |
| `.claude/scripts/archive-done.ps1` | Moves Done task files to `docs/tasks/archive/` on a branch, ready to commit |
| `.claude/scripts/next-id.ps1` | Next free decision ID (or roadmap IDs in use) across every open PR branch |
| `.claude/scripts/list-follow-ups.ps1` | Follow-ups listed in merged PR bodies, for `/track-follow-ups` |
| `.claude/scripts/lib-tasks.ps1` | Shared task-file parser |
| `docs/templates/` | Templates for the brief, feature list, architecture doc, task list, decisions log, owner checklist, UX floor, `/verify` skill, review protocol and findings ledger |
| `docs/templates/github/` | Optional workflows: hand-run release, performance budget on previews, nightly backup with a restore drill, dependency bot |
| `docs/tasks/_TEMPLATE.md` | Task file template |
| `docs/tasks/.gitignore` | Keeps the generated `INDEX.md` out of git |
| `.github/workflows/ci.yml` | CI gate template (`verify` job), filled by `/customize-kit` |
| `.github/workflows/claude-pr-review.yml` | Optional: Claude reviews PRs when they leave draft; skips cleanly without its secret |
| `.github/workflows/claude.yml` | Optional: `@claude` in issues and PR comments; skips cleanly without its secret |
| `.github/pull_request_template.md` | PR body: What, Why, ACs, How it was verified (one row per ready gate), manual steps, Follow-ups (each with where it went) |

Files the kit never ships, so an upgrade never touches them: `.claude/project/*.md` (your overrides), `.claude/skills/verify/SKILL.md` (generated by `/customize-kit`), and your decisions log (created from the template at the path your Project docs table names).

## Requirements

Windows with PowerShell 5.1+ and Git for Windows; Claude Code v2.1.139+; GitHub CLI; Node.js 18+ for the browser checks; a Claude Pro, Max, Team, or Enterprise plan.
