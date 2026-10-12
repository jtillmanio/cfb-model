# implement-task: project section

Read by `/implement-task` (and so by `/next-task`, which hands over to it) at the start. It wins where it conflicts with the skill, except for the kit's floor.

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
