# {{PROJECT_NAME}}

{{One paragraph: what the app does, who uses it, and the one or two things that make it non-trivial (data volume, offline use, multi-user, etc.).}}

## Commands

Environment: Windows. Give the user PowerShell syntax. Commands below must also run under `cmd.exe /c` because the hooks execute them that way.

`.claude/kit.json` is the single source of truth for verification commands (`verify.fast` runs after every edit, `verify.full` is what the test-runner agent runs). Keep this table in sync with it.

| Purpose | Command |
|---|---|
| Install dependencies | `{{...}}` |
| Run dev server | `{{...}}` |
| Typecheck / compile | `{{...}}` |
| Lint | `{{...}}` |
| Unit / integration tests | `{{...}}` |
| Single test file | `{{...}}` |
| Production build | `{{...}}` |
| Apply DB migrations | `{{...}}` |
| Seed / load data | `{{...}}` |

## Where things live

- Architecture: `docs/architecture.md`
- Design source of truth: `{{design/...}}` — read the file; do not work from a prose description of it
- Tasks: `docs/tasks/` — `INDEX.md` is the board, one file per task
- Decisions: `docs/decisions.md` — settled; do not reopen unless the user asks
- {{Other key directories, one line each}}

## Hard rules

Only rules a reviewer can check against a diff. The spec-reviewer agent enforces this list.

1. {{e.g. "Never store derived values; compute them in views or queries."}}
2. {{e.g. "Every per-user table is keyed by (user_id, entity_id)."}}
3. {{e.g. "No new runtime dependency without a decisions-log entry."}}
4. Never edit files matched by `protectedPaths` in `.claude/kit.json`. If one must change, stop and ask.

## Conventions

- {{Naming, folder structure, error handling, logging, test file location}}
- {{Styling approach and where design tokens live}}

## Workflow

- One task per session. Attended: `/clear`, then `/implement-task TASK-###` or `/next-task`. Unattended sessions are started by `.claude/scripts/dispatch-approved.ps1`.
- No code before the plan is approved (`plan_status: approved` in the task file). The plan lives in the task file's `## Plan` section.
- If the spec is ambiguous or contradicts the code, ask. Never guess, never silently widen scope, never rewrite acceptance criteria.
- Change files outside the plan's file list only after explaining why.
- Done = test-runner green, test-auditor PASS, every applicable reviewer APPROVE, CI green, and the user's manual check. Claude sets `Review`; only the user's "accepted" sets `Done`.
- Never hand-edit `docs/tasks/INDEX.md`. Run `.claude/scripts/build-index.ps1`.
- Post-edit check failures in the middle of a multi-file change are expected. Finish the change, then fix whatever still fails.

## Git

- Work on `task/<id>-<slug>` branches. Commit freely on them (conventional commits, task ID in the scope).
- Push only the task branch (`git push -u origin task/...`). Never push, force-push, or merge the base branch. Permissions deny it and branch protection enforces it.
- PRs open as drafts and are marked ready only after CI passes.

## Gotchas

Add a line every time the user corrects the same mistake twice.

- {{...}}
