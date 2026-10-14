# Git: testing on the branch and opening the PR

Moved word for word from `.claude/rules/git.md`, which loads in every session and keeps a summary under the same headings. Read this before pushing. Values in backticks such as `workflow.readyGates` are keys in `.claude/kit.json`.

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
- The body follows `.github/pull_request_template.md`: What · Why · Acceptance criteria · How it was verified · Manual verification · Follow-ups · Reviewer checklist. Every Follow-ups bullet ends `→ <path> § <section>` or `→ not tracked: <reason>`.
- Watch CI with `gh pr checks <n> --watch`. Fix a red check on the same branch with a new commit.
- Mark it ready (`gh pr ready <n>`) only after the ready gates above.
