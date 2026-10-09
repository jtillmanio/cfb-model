---
name: verify
description: Full local verification gate for this project — every command in verify.full, the same set CI runs. Run before pushing any branch.
---

<!-- Template for .claude/skills/verify/SKILL.md. /customize-kit fills the {{...}} parts from
     verify.full in .claude/kit.json and writes the result there. The kit never ships a file at
     that path, so an upgrade never overwrites the generated skill. Delete this comment. -->

# Verify

Run these in order from the project root and report the actual output, not a summary. Don't stop at the first failure: run every command, because a failing typecheck and a failing test are separate signals. Fix root causes; never suppress an error to get a pass.

```powershell
{{one line per verify.full command, in order}}
```

{{One paragraph per command that needs explaining: what a chain runs and that it stops at its first failing step; which commands need a database or an env variable.}}

Tests touch the test database only. If {{the test database variable}} is unset, run the commands that don't need a database, say plainly which suites ran only in CI, and never point them at another database.

This is the local half of "Test on the branch" in `.claude/rules/git.md`. CI and any other ready gates in `workflow.readyGates` still have to pass on the branch.

Then show evidence: each command you ran, its exit code, and the lines that matter. Do not claim success without it.
