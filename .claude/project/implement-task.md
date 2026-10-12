# implement-task: project section

Read by `/implement-task` (and so by `/next-task`, which hands over to it) at the start. It wins where it conflicts with the skill, except for the kit's floor.

## Push and open the PR without asking

In attended mode, Phase 6 does **not** ask "Push and open a draft PR?". Once the close-out commit is made and every reviewer has approved, push the task branch and open the draft PR straight away, exactly as unattended mode does. Then continue into Phase 7 (ready gates).

- **Why:** the owner reviews the work on the PR, and asking first only adds a round trip (owner's instruction, 2026-10-09).
- **Unchanged:** push only the task branch with `git push -u origin <task-branch>`. Never push to `main`, never force-push, never merge, never start a deploy. The PR still opens as a draft and is marked ready only after the ready gates pass.
- **Follow-up approvals are still asked.** If Phase 6's Follow-ups step has approvals (planning-doc edits), ask for them as the numbered list, just without the push question; whatever isn't approved goes to the **Owner checklist**.
- **Still stop and ask** when something other than this prompt calls for it: a Blocked task, a failing gate the owner must fix (`ownerFix`), or a SPEC GAP.
