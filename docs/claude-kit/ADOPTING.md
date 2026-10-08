# Adopting the kit into an existing project

For projects that already have some combination of planning docs, a finished design, a repo, CI, a database, hosting, and code. Your existing files keep their names and locations. The kit maps itself onto them.

## Which guide do you need?

| Your project has | Use |
|---|---|
| An idea or a brainstorm only | `KICKOFF.md` |
| Docs and/or design, no code | This guide; `/adopt` routes you to `/skeleton` if there's no toolchain |
| Docs, design, and phase 0 done (repo, CI, DB, hosting) | **This guide** |
| Code but no planning docs | This guide; `/adopt` will flag scope and architecture gaps, and you fill them with `/product-brief` and `/architecture` |

## The adoption pipeline

| # | Step | Command | Output | Exit criteria | Time |
|---|---|---|---|---|---|
| 1 | Pre-flight | Manual checklist below | — | All items checked | 10–20 min |
| 2 | Install the kit | PowerShell, below | Kit files, collisions resolved | Skills load; nothing of yours overwritten | 15 min |
| 3 | Adopt | `/adopt` | `docs/kit-adoption.md`, CLAUDE.md "Project docs" map, `docs/decisions.md` | Role map confirmed; gap report reviewed | 30–45 min |
| 4 | Fix blocking gaps | Continue `/adopt` (its gate) | Sections appended to your docs | No **BLOCKS TASKS** gaps left | 30–90 min |
| 5 | Configure | `/customize-kit` | `kit.json`, agents, permissions, CI notes | Smoke tests pass | 20–40 min |
| 6 | GitHub | Web UI | Ruleset on the existing CI job | Base branch protected | 10 min |
| 7 | Plan | `/milestones <your roadmap>` | Task list with milestones and stubs | Coverage 100%; built work excluded | 30–60 min |
| 8 | First tasks | `/new-task <task list> M1` | M1 task files | Reviewed and `Ready` | 30 min |
| 9 | Build | `/next-task` | PRs | First 3 tasks attended | — |

Times are rough, for a small project. Steps 3 and 4 are where accuracy is won: every acceptance criterion written later traces back to what they settle.

---

## Step 1: Pre-flight checklist

| Check | Why | How |
|---|---|---|
| Working tree clean | `/adopt` and `/customize-kit` commit on branches | `git status` |
| In-flight branches merged or parked | The kit's tasks will touch the same files | `gh pr list`; `git branch -r --no-merged` |
| Baseline green | The post-edit hook flags every pre-existing error on every edit | Run your test, lint, and typecheck commands |
| Local/dev database separate from production | Agents run migrations and seeds | Confirm `.env.local` points at a local or dev DB, never production |
| You know your CI job names | Branch protection requires them by name | Actions tab → a recent run → job names |
| Design is committed | Agents can only read what's in the repo | Handoff, exports, and screenshots under one folder, e.g. `design/handoff/` |

If the baseline isn't green, fix it first, or record the failures as known and add a "fix baseline" task to M1. The kit works much better against a green baseline.

## Step 2: Install into an existing repo

The kit lives at `C:\Development\tools\claude-code-starter-kit\` (one-time setup: USER-GUIDE §3.1).

```powershell
git switch -c chore/adopt-claude-kit
powershell -NoProfile -ExecutionPolicy Bypass -File C:\Development\tools\claude-code-starter-kit\install-kit.ps1 -WhatIf   # preview: what gets added, merged, or skipped
powershell -NoProfile -ExecutionPolicy Bypass -File C:\Development\tools\claude-code-starter-kit\install-kit.ps1
```

The installer handles collisions for you:

| Situation | What the installer does | What you do |
|---|---|---|
| You already have `CLAUDE.md`, `.claude/settings.json`, a PR template, or `docs/decisions.md` | Leaves yours untouched; writes the kit's version to `.kit-incoming\<same path>` | Run the merge prompt it prints, or let `/adopt` merge them (it checks `.kit-incoming\` first) |
| You already have CI, under any filename | Skips the kit's placeholder `ci.yml`, which would otherwise fail every PR | Nothing; `/customize-kit` checks that your CI runs the full gate |
| You already have `docs/tasks/` | Adds the template beside your files | `/adopt` flags task files whose front matter doesn't match the kit's |

Restart Claude Code. Type `/` and confirm `adopt` is listed. Commit (`chore: add Claude Code kit`), but don't merge yet. Steps 3–5 go on the same branch, so they land in one reviewable PR.

## Step 3: `/adopt`

```text
/model opus
/adopt
```

Add hints when you know them; they save a round of questions:

```text
/adopt design source of truth is design/handoff/ (designs/, screenshots/, tokens/); roadmap is docs/06-roadmap.md; designs win over docs; put the task list at docs/08-tasklist.md
```

What it does, in order:

1. **Preconditions.** Checks for a clean tree and kit collisions, and lists in-flight PRs and branches.
2. **Discovery** (read-only). Inventories docs, design, stack, scripts, tests, CI jobs, database and migrations, hosting config, issues, and roadmap.
3. **Role map plus questions** (gate). Proposes which of your files plays each kit role and checks what's already built against the code. Then asks up to 8 questions in one batch.
4. **Writes:**
   - the "Project docs" table in `CLAUDE.md`, which every skill and agent reads to find your files;
   - `docs/decisions.md`, with decisions extracted from your docs and design, each citing its source;
   - `docs/kit-adoption.md`: role map, design inventory with proposed S-IDs, toolchain inventory, built-state table, gap report, and the inputs for `/customize-kit` and `/milestones`.

### Review `docs/kit-adoption.md` (15–20 minutes)

| Section | Check |
|---|---|
| Role map | Every file you rely on is mapped; nothing important is `—` by mistake |
| Built-state table | Nothing marked "built" that's actually half-done (otherwise it gets excluded from planning) |
| Design inventory | Every designed screen is listed; S-IDs are sensible; mismatches have a resolution |
| Toolchain inventory | Missing scripts are listed as task stubs, not silently assumed |
| Gap report | Each **BLOCKS TASKS** item has a fix you agree with |

## Step 4: Fix the blocking gaps

`/adopt` stops and asks which gaps to fix. Approve the **BLOCKS TASKS** set at least. The usual ones:

| Gap | Fix (appended, never rewritten) |
|---|---|
| No feature IDs, MVP cut, or outcomes | F-IDs, priority column, and 2–3 observable outcomes per MVP feature, in your product doc |
| No screen IDs or missing states | "Screen inventory (from design)" table in your design brief; missing states resolved by designing them or by a "use defaults" note |
| Testing strategy or seed data missing | Section in your architecture doc, with seed values that match the screenshots where practical |
| Non-UI logic with no measurable acceptance | Evaluation metrics, protocol, and baseline in that domain spec |
| Missing scripts (test, e2e, typecheck…) | Become M1 task stubs |
| Roadmap phases are layers, not slices | Resolved in step 7; `/milestones` reshapes them and explains why |

**BLOCKS UNATTENDED** gaps can wait until you're ready for Level 2.

## Step 5: `/customize-kit`

It reads `docs/kit-adoption.md` first, so it doesn't re-ask what `/adopt` settled. For an existing project it:

- fills `kit.json` from your real scripts, and runs and times each one;
- applies the design entries:
  - `ui.designFiles` from your design inventory
  - `protectedPaths` for the design source of truth and applied migrations
  - the token hard rule
- keeps your CI, proposes deleting the kit's `ci.yml`, and checks that your CI runs the full gate on PRs;
- adds permission allow-rules for your commands;
- merges the kit's PR checklist into your template;
- tailors the agents: data rules for schema-reviewer, design comparison for ui-verifier.

**If your repo has several apps** (e.g. a web app plus a Python service): `kit.json` takes one command list per check. Put both apps' commands in `verify.full`, list both sets of extensions in `sourceExtensions`, and, if their test runners differ, have `/customize-kit` add a small wrapper script for `testAudit.run` that routes each test file to the right runner.

Merge the adoption PR once its CI is green.

## Step 6: GitHub

Follow USER-GUIDE §5.1, with one difference: under "Require status checks", add **your existing CI job name(s)**, not `verify`. Do §5.2 (Claude GitHub App) only if you want Claude's PR reviews or `@claude`.

## Step 7: `/milestones`

```text
/milestones docs/06-roadmap.md
```

Using your roadmap as the source, it:
- keeps your phases unless they break the milestone rules (demoable slices, riskiest first, 3–8 tasks), and explains each change;
- excludes work marked **built**, and scopes only the missing part of **partial** items;
- schedules the toolchain-gap stubs in M1;
- has every UI stub cite its S-ID, design file, and reference screenshot;
- checks coverage against your feature IDs, S-IDs, and data model;
- writes to the task-list path in your "Project docs" map.

## Step 8: First tasks

```text
/new-task docs/08-tasklist.md M1
```

Review each file, set `Ready`, commit, push. Then:

```text
/clear
/next-task
```

Run the first three tasks **attended**, even ones marked `unattended`. They establish the patterns later tasks copy, and they show you whether the adoption missed anything. Watch for:

- the plan citing the wrong doc;
- an AC that can't be checked;
- a design file not being read.

Each one points to a fix in the "Project docs" map or the gap report.

---

## Common situations

| Situation | What to do |
|---|---|
| Roadmap partly implemented | Trust `/adopt`'s built-state table after you've reviewed it; `/milestones` plans only what's left |
| Open GitHub issues | `/adopt` lists them; turn in-scope ones into tasks with `/new-task "<issue title> (#12)"`. Put `Closes #12` in the PR body |
| No tests at all | M1 starts with "test harness + tests for the main flow". Leave `testAudit.run` empty until it exists; test-auditor runs static-only meanwhile |
| Only a production database | Create a local or dev database before any task runs migrations. Never put production credentials where agents can read them |
| Hosting with preview deploys | Keep ui-verifier on the local dev server (`ui.startCommand`). Use previews for your own manual check in PR review |
| Design lives in Figma or another tool | Export screens as images plus any tokens into `design/`, and map them as the design source of truth. Same flow from there |
| Backend-only or no UI | Set the design roles to `—`; delete the ui-verifier when `/customize-kit` asks |
| Docs are out of date versus the code | Tell `/adopt` which wins for each conflict; it records each decision in `docs/decisions.md` so it doesn't come up again |
| Existing `CLAUDE.md` with lots of content | `/adopt` merges the kit's sections in; keep the total under ~100 lines by moving reference material into docs and linking to it |

## Example role map: numbered docs plus a design handoff

| Kit role | Example path |
|---|---|
| Product brief, Features | `docs/01-product.md` |
| Architecture | `docs/02-architecture.md` |
| Data model | `docs/03-data-model.md` |
| Domain specs | `docs/04-model.md` |
| Design brief / intent, Screen inventory | `docs/05-ui-design-brief.md` (inventory appended by `/adopt`) |
| Roadmap (source) | `docs/06-roadmap.md` |
| Design process notes | `docs/07-claude-design-playbook.md` |
| Task list | `docs/08-tasklist.md` |
| Design source of truth | `design/handoff/designs/` |
| Design tokens | `design/handoff/tokens/` |
| Reference screenshots | `design/handoff/screenshots/` |
| Decisions | `docs/decisions.md` |
| Tasks | `docs/tasks/` |

## Without the `/adopt` skill (fallback prompt)

If you're using an older kit or the skill isn't loading, this prompt does the core of steps 3–4:

```text
We're adopting the Claude Code starter kit (guides in docs/claude-kit/) into this existing project.
Do not rename, move, reformat, or rewrite any existing doc, design file, or code. Append only, after my approval.

1. Inventory docs, design (look at screenshots; read any README or manifest), stack, scripts, tests, CI job names,
   database and migrations, hosting config, open issues, and the roadmap.
2. Propose a role map (product brief, features, screen inventory, design intent, design source of truth, tokens,
   screenshots, design process notes, architecture, data model, domain specs, roadmap, task list, decisions)
   and classify each roadmap item as built, partial, or not built, with file:line evidence.
   Ask me up to 8 questions in one batch, then stop.
3. After my answers: write the "Project docs" table in CLAUDE.md, extract decisions into docs/decisions.md
   (citing sources), and write docs/kit-adoption.md with the role map, design inventory with proposed S-IDs,
   toolchain inventory, built-state table, and a gap report. Classify each gap as BLOCKS TASKS,
   BLOCKS UNATTENDED, or NICE, with a fix (doc section, task stub, or decision).
4. Stop and ask which gaps to fix.
```
