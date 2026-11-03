---
id: TASK-059
title: Keep the auth-proxy branch's newest preview in the Vercel cleanup
status: Review
depends_on: []
size: S
model: sonnet
autonomy: attended
ui: false
plan_status: approved
planned_at_commit: 80e65d8
---

# TASK-059 — Keep the auth-proxy branch's newest preview in the Vercel cleanup

## Goal

The Vercel cleanup never deletes the deployment behind the `auth-proxy` branch's stable URL, so preview sign-in (TASK-060) keeps working after the weekly sweep.

## Context

- Asked for by the owner on 2026-11-03: sign-in doesn't work on previews, so branches can't be tested there. The owner chose a dedicated preview proxy: a long-lived `auth-proxy` branch whose Vercel branch alias (`cfb-model-git-auth-proxy-<scope>.vercel.app`) is the callback of a third GitHub OAuth app, "CFB Model (preview)". TASK-060 builds the sign-in side.
- That branch has no PR. Today's sweep deletes "previews with no open PR (a day old or more)" (`.github/workflows/vercel-cleanup.yml` header; `plan_cleanup` in `python/db/src/db/deployments.py`), so the proxy's deployment would be gone by the next Monday 06:15 ET run and the branch alias would point at nothing.
- Only the newest ready deployment of the branch needs to survive: the branch alias follows it. Older `auth-proxy` builds can go as usual.
- Decisions: D-126 (what the cleanup deletes and keeps), D-102 (no preview sign-in, revisited by TASK-060).
- Editing `vercel-cleanup.yml` runs the "Changed workflow run on the branch" ready gate. A hand run is a dry run unless `dry_run=false`, so the gate's run deletes nothing.

## Acceptance criteria

- [x] AC-1: Given a sweep over READY previews of branch `auth-proxy`, none with an open PR and all more than a day old, `plan_cleanup` keeps exactly the newest one (verdict `delete=False`, with a reason naming the auth proxy) and deletes the older ones with the usual no-open-PR reason (pytest).
- [x] AC-2: Given a `--branch auth-proxy` run (the PR-closed mode), the newest READY `auth-proxy` build is still kept and the older ones are deleted (pytest).
- [x] AC-3: Given an `auth-proxy` build that is still building next to a READY one, both are kept. The building one is kept by the existing rule and the READY one as the proxy (pytest).
- [x] AC-4: Previews of every other branch with no open PR are deleted exactly as before: the existing `test_deployments.py` cases pass unchanged.
- [x] AC-5: The `vercel-cleanup.yml` header's "Never deleted" list and the `deployments.py` module docstring both name the newest ready `auth-proxy` preview. The branch name is one constant in `deployments.py`.

## Out of scope

- The sign-in proxy itself, the OAuth app and the Preview env vars (TASK-060).
- Keeping the `auth-proxy` branch's Neon preview database. The Neon cleanup runs only when a PR closes, and this branch has none.
- Any change to the `main` build or production rules.

## Files likely touched

- `python/db/src/db/deployments.py`: the keep rule, the constant and the docstring.
- `python/db/tests/test_deployments.py`: AC-1 to AC-3.
- `.github/workflows/vercel-cleanup.yml`: the header comment only.

## Verification

- Automated: `uv --directory python run pytest db/tests/test_deployments.py`, with the new cases failing on the old code first.
- Manual: `gh workflow run vercel-cleanup.yml --ref <branch>` (dry run), then read the summary. Expected: once the `auth-proxy` branch exists, its newest preview is listed as kept with the proxy reason. Before then, nothing changes.

## Follow-ups

_Work noticed during this task and deliberately left out. Each bullet ends `→ <path> § <section>` (where it was placed) or `→ not tracked: <reason>`. See `.claude/skills/track-follow-ups/classify.md`; the PR's Follow-ups section is copied from here._

- Candidate decision: the cleanup keeps the newest ready `auth-proxy` preview, which amends D-126 (spec review R1) → docs/decisions.md § D-153
- README › the Vercel cleanup's "never deletes" sentence doesn't name the proxy preview (spec review R1, optional) → not tracked: that sentence was already a partial list (it also omits "not built from git"). D-126, D-153, the workflow header and the module docstring are the complete lists.

## Plan

Approved by the owner on 2026-11-03.

**Steps:**

1. Write the tests first, in `python/db/tests/test_deployments.py`, and show each failing on the old code:
   - `test_a_sweep_keeps_only_the_newest_ready_auth_proxy_preview` (AC-1): three READY `auth-proxy` previews, all over a day old, none with an open PR. The newest is kept with the proxy reason; the older two are `(True, "preview with no open PR")`.
   - `test_branch_mode_keeps_the_newest_ready_auth_proxy_preview` (AC-2): the same builds with `branch="auth-proxy"`. The newest is kept and the older ones are deleted.
   - `test_a_building_auth_proxy_preview_does_not_displace_the_ready_one` (AC-3): a BUILDING build newer than a READY one. The BUILDING one is kept as "still building" and the READY one as the proxy.
2. `python/db/src/db/deployments.py`:
   - Add the constant `AUTH_PROXY = "auth-proxy"`.
   - In `plan_cleanup`, work out `newest_proxy`: the first READY, non-main build on `AUTH_PROXY`, from the same newest-first list `newest_main` uses.
   - Keep that build with the reason `"the auth proxy's newest ready preview"`. The check sits after the main-build branch and before the open-PR, fresh and delete rules.
   - Add the proxy preview to the module docstring's "Never deleted" list (AC-5).
3. `.github/workflows/vercel-cleanup.yml`: header comment only. Add the newest ready `auth-proxy` preview (the preview sign-in proxy, TASK-060) to "Never deleted" (AC-5).

**Files:** `python/db/src/db/deployments.py`, `python/db/tests/test_deployments.py`, `.github/workflows/vercel-cleanup.yml`, and this task file.

**Test strategy:**

- AC-1 to AC-3: the three new tests.
- AC-4: the existing `test_deployments.py` cases, passing unchanged.
- AC-5: spec-reviewer reads the docstring and the header comment.

**Risks:**

- The workflow edit triggers the "Changed workflow run on the branch" gate. Its run is a dry run (`gh workflow run vercel-cleanup.yml --ref <branch>`), so it deletes nothing.
- Until the `auth-proxy` branch exists, the new rule changes nothing.

## Review log

Verify R1 PASS | Audit R1 NOT RUN (untracked TASK-060 file; excluded locally at the owner's choice) → R1 PASS | Spec R1 CHANGES (D-126 out of date) → R2 APPROVE

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds: 1
- Review rounds: 2
- First-pass AC FAILs: 0
- Plan revisions after approval: 0
