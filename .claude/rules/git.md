# Git & PR rules

- **Never commit to `main`.** The one exception is the Phase 0 bootstrap commit that creates `main` when the GitHub repo is created. A free private repo has no branch protection, so this rule is the protection.
- Branch names: `feat/…`, `fix/…`, `chore/…`, `docs/…`, `model/…` (model experiments).
- Stage by path. Never `git add -A` or `git add .`.
- Commit messages: imperative summary line ≤ 72 chars, blank line, body explaining *why*.
- One task per PR. The owner squash-merges; Claude never merges.
- **Every fix or feature needs a test that fails without the change.** Show it failing on the old code first. A test written afterward that passes immediately proves nothing.
- Before calling a PR ready: the full CI suite passes locally, CI is green, and the Vercel preview has deployed.
- Test a changed workflow on its branch: `gh workflow run <file> --ref <branch>`.
- Merging does not deploy. Production changes go out only through the `release` workflow.
