<!-- /implement-task fills this in. For PRs you open yourself, fill what applies.
     The title is a commit subject (workflow.commitFormat in .claude/kit.json), because
     the squash merge keeps it. This body is what the base branch keeps. -->

## What

<!-- The change in a few bullets. Task work: "TASK-014: Show run progress (docs/tasks/TASK-014-run-progress.md)". -->
-

## Why

<!-- The problem, with task, roadmap, decision and review-finding IDs. -->

## Acceptance criteria

<!-- Roadmap mode: the roadmap's check line first, verbatim. Then the task file's ACs; tick each when verified. -->
- [ ] AC-1:
- [ ] AC-2:

## How it was verified

<!-- One row per reviewer, then one row per ready gate (workflow.readyGates), in order. Owner gates say "owner".
     Say which suites ran only in CI. Anything that can only be checked after merge: name it,
     say why, and give the exact check to run straight after. -->

| Check | Where | Result |
|---|---|---|
| test-runner (`verify.full`) | local | |
| test-auditor | local | |
| spec-reviewer | local | |
| schema-reviewer | local | n/a |
| ui-verifier | local dev server | n/a |
| CI | GitHub | see checks below |

<!-- Screenshots from ui-verifier, if any -->

### Manual verification (owner)

<!-- Steps from the task's Verification section, each with its expected result -->
1.

## Follow-ups

<!-- Work noticed and deliberately left out (copied from the task file's ## Follow-ups). Each bullet ends with
     where it was placed, per workflow.followUps (.claude/skills/track-follow-ups/classify.md), or why not:
       - 1.3c: a range like #5-5 is a bad_range; the error copy should say why → docs/tasks/TASK-005-range-errors.md § Context
       - Candidate decision: suggestions use pg_trgm's 0.3 threshold → docs/decisions.md § D-24
       - Set the RESEND_API_KEY secret in production → docs/owner-checklist.md § Actions
       - Leading zeros aren't canonicalised → not tracked: done in this PR (plan revision)
     Approvals waiting in the Owner checklist say so. Review-finding IDs this PR addresses or opens. -->
-

## Reviewer checklist (owner)

- [ ] Ran the manual steps above and got the expected results
- [ ] Every owner gate in the table above has passed
- [ ] Diff contains only what the task asked for (no surprise files), plus the follow-up placements listed above
- [ ] Each follow-up went where the work that will do it will read it (move or drop any you disagree with)
- [ ] No secrets, env files, protected files or production config touched
- [ ] Task file set to `status: Done` (reply "accepted" to the session, or edit it in this PR) before merging. Accepting also moves it to `docs/tasks/archive/`; a hand edit leaves that to the next task's close-out
- [ ] After the squash merge, any deploy step the project has (merged is not live)
