# implement-task: project section

Read by `/implement-task` (and so by `/next-task`, which hands over to it) at the start. It wins where it conflicts with the skill, except for the kit's floor.

## Implement on the task's model (attended only)

Before Phase 2, in attended mode only: compare the task's `model:` front matter (`opus`, `sonnet`, `haiku`) with the model family this session runs on. If they differ, stop before writing any code and tell the owner to run, in order: `/clear`, `/model <x>`, `/implement-task TASK-###`, where `<x>` is the task's `model:`. Leave the branch and the task file as they are; the re-run's Phase 0 finds the approved plan and goes straight to Phase 2.

- **Why:** `model:` only took effect in unattended runs, so attended tasks were implemented on whatever model the session happened to be on (owner's instruction, 2026-10-14).
- **Planning is unaffected:** Phase 1 runs on the session's model (the task template says planning always uses Opus). The check sits between plan approval and the first edit.
- **Unattended runs skip this:** `.claude/scripts/dispatch-approved.ps1` already starts them with `--model`.

## Push and open the PR without asking

In attended mode, Phase 6 does **not** ask "Push and open a draft PR?". Once the close-out commit is made and every reviewer has approved, push the task branch and open the draft PR straight away, exactly as unattended mode does. Then continue into Phase 7 (ready gates).

- **Why:** the owner reviews the work on the PR, and asking first only adds a round trip (owner's instruction, 2026-10-09).
- **Unchanged:** push only the task branch with `git push -u origin <task-branch>`. Never push to `main`, never force-push, never merge, never start a deploy.

## Mark the PR ready as soon as it's open

Right after `gh pr create` (and the link commit), run `gh pr ready <n>`. Don't hold the PR in draft for Phase 7: a draft can't be merged, and a gate only the owner can clear (a cancelled Vercel preview, an owner-run workflow) left it stuck in draft (TASK-005, PR #24). This wins over "mark it ready only after the ready gates" in `.claude/rules/git.md` and the skill's Phase 7 step 5.

- **Why:** the owner reviews and merges from the PR and wants it mergeable once it's open (owner's instruction, 2026-10-12).
- **The gates still run.** Phase 7 continues after the PR is ready: watch CI and the other gates, fix failures on the branch, and list every gate's result (passed, failed, or waiting on the owner) in the PR's verification table and the final report. A failing gate is reported plainly; the PR is not put back into draft.
- **Applies to every PR Claude opens** in this repo (task PRs, docs/ and chore/ PRs), unless the owner asks for a draft.
- **Follow-up approvals are still asked.** If Phase 6's Follow-ups step has approvals (planning-doc edits), ask for them as the numbered list, just without the push question; whatever isn't approved goes to the **Owner checklist**.
- **Still stop and ask** when something other than this prompt calls for it: a Blocked task, a failing gate the owner must fix (`ownerFix`), or a SPEC GAP.

## Size check limits

Phase 1's size check uses this project's limits, set in `.claude/project/new-task.md` › Size limits. A task fails it at more than 12 files (not 8), or with schema and UI together.

- **Why:** 8 files forced splits that only separated code from its doc edits (owner's instruction, 2026-10-16).
