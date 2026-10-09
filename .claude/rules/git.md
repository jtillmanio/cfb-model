# Git: branches, commits, PRs

Loaded in every session (no `paths:` frontmatter). The kit's skills follow these rules too. Values in backticks such as `workflow.staging` are keys in `.claude/kit.json`, which is the one place they are set; this file says what they mean. `/customize-kit` adds the project-specific lines under "Project notes" at the end.

## Never commit on the base branch

The base branch is `workflow.baseBranch` (default `main`). Every change reaches it through a PR, including a one-line doc fix and approved task plans. Never commit while it is checked out, never push to it, never force-push it.

Start each piece of work from an up-to-date base:

```bash
git switch <base>
git pull --ff-only
git switch -c <branch>
```

If the working tree already holds changes you didn't make, leave them alone: they are the owner's work in progress. Don't stash, reset, or commit them.

## Branch names

Lowercase and hyphenated, one purpose per branch, with a prefix from `workflow.branchPrefixes` (default `task/`, `fix/`, `docs/`, `chore/`):

| Work | Branch |
|---|---|
| A task file | `workflow.taskBranch` (default `task/{id}-{slug}`). In roadmap mode (`workflow.roadmap`) the id is the roadmap ID, e.g. `task/1.3-bulk-parser`. A pattern starting with `{type}/` (e.g. `{type}/{id}-{slug}`) takes the prefix that fits the task, e.g. `feat/014-run-progress` or `fix/021-date-format` |
| A bug outside a task | `fix/<slug>` |
| Docs only, including approved plans | `docs/<slug>`, e.g. `docs/plans-2026-10-09` |
| Tooling, CI, dependencies, config | `chore/<slug>` |

A dependency bot's own branches (e.g. `dependabot/...`) are the one exception. Its PRs pass the same CI.

One task per branch, one branch per PR. A problem that belongs to another task goes in the PR's Follow-ups, not in this diff.

## Staging

`workflow.staging` is `by-path` unless the project set `all`.

- **by-path** (default): stage named files, `git add <file> <file>`. Never `git add -A`, `git add --all`, `git add .`, or `git commit -a`; they sweep in the owner's edits, env files, and scratch output. The settings deny them.
- Before every commit, run `git status` and `git diff --staged`, and read what is actually staged.
- If a file holds both your change and the owner's uncommitted edits, stage only your hunks (write a patch and `git apply --cached`; `git add -p` is interactive and unavailable), or ask.
- **all**: the 2.3.1 behaviour, `git add -A`. Only for projects whose tree never holds anything but Claude's work. The settings deny rules must be removed to match.

## Commit messages

`workflow.commitFormat` picks the subject line:

| Format | Subject | Example |
|---|---|---|
| `conventional` (default) | `<type>(<scope>): <summary>` | `feat(TASK-014): show run progress` |
| `area` | `<area>: <imperative, lowercase>` | `task 1.3: parse bulk-entry labels`, `ci: cache npm` |

For `area`, the area is `task <id>` for task work, otherwise the part of the repo (`ci`, `db`, `ui`, `docs`, `deps`, `claude`...).

Both formats:

- Subject at most 72 characters, imperative, no trailing period.
- The body explains *why*: the failure fixed, the constraint respected, what was ruled out. The diff already says what. Cite the IDs the docs use (task, decision, review finding).
- End with the attribution trailer the session gives you.
- Several commits per branch are fine. PRs are squash-merged, so the PR title and body are what the base branch keeps.
- Never `--no-verify`. Never `--amend` a commit that is already pushed.

## Test on the branch, before the PR is ready

A PR is ready only when everything that can prove the change has run **against the branch** and passed. The checks are `workflow.readyGates`, in order (default: `verify.full` locally, then CI). Each gate is checked by Claude or by the owner; Claude marks a PR ready only when every gate it can check has passed, and lists the owner's gates in its report.

Before pushing, run `/verify` if the project has it (otherwise the `verify.full` commands). Tests touch the test database only, never a development or production one. If a suite can't run locally (no test database), say which suites ran locally and which only in CI. Never point a test at another database to make it run.

Something that truly can't run before merge (a production-only behaviour, the deploy itself) goes in the PR's "How it was verified" table with the reason and the exact check to run straight after merge. That is the exception.

## Push and open the PR

```bash
git push -u origin <branch>
gh pr create --draft --base <base> --title "<a commit subject>" --body-file <file outside the repo>
```

- The PR title is a commit subject in `workflow.commitFormat`, because the squash merge keeps it.
- The body follows `.github/pull_request_template.md`: What · Why · Acceptance criteria · How it was verified · Manual verification · Follow-ups · Reviewer checklist.
- Watch CI with `gh pr checks <n> --watch`. Fix a red check on the same branch with a new commit.
- Mark it ready (`gh pr ready <n>`) only after the ready gates above.

## Merging and deploying

The owner merges, with **Squash and merge**. Claude never runs `gh pr merge`. After a merge: `git switch <base>`, `git pull --ff-only`, delete the local branch.

Merged is not live. If the project has a deploy step (the **Deploy** role in `CLAUDE.md`), the owner runs it; Claude never starts a deploy or release, dry run included, unless the owner says so for that release. `workflow.afterMerge` is the line every final report ends with.

## Rebasing

Rebase a branch on the base only when it conflicts or is stale enough to matter. `workflow.allowForceWithLease` (default `false`) decides what happens next:

- `false`: never force-push. Merge the base into the branch instead.
- `true`: after a rebase, push with `--force-with-lease`, only to your own branch, never plain `--force`.

## Project notes

- **Branch prefixes** (`workflow.branchPrefixes`): `feat/` new behaviour, `fix/` a bug, `chore/` tooling, CI, dependencies and config, `docs/` docs only, `model/` model experiments. Task branches take the prefix that fits the task (`workflow.taskBranch` is `{type}/{id}-{slug}`).
- **Every fix or feature needs a test that fails without the change.** Show it failing on the old code first. A test written afterward that passes immediately proves nothing.
- **Merging does not deploy.** Vercel builds every commit on `main` but doesn't promote it; production changes go out only through the `release` workflow (not built yet; roadmap Phase 0).
- **No branch protection is available on this repository** (a free private repo: rulesets return 403). These rules and the settings deny rules are the only guard.
- **Never commit** `.env` or any `.env.*` except `.env.example` (`.env.live` holds the production URL), the local data lake under `/data/`, or `*.duckdb` files.
