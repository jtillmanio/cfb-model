# Kickoff: from idea to first task

How to take a project from a brainstorm to Ready task files, using Claude chat, Claude Design, and Claude Code with this kit. Once tasks exist, `USER-GUIDE.md` §7–8 takes over.

## The pipeline

| # | Stage | Where | Model | You produce | Exit criteria |
|---|---|---|---|---|---|
| 0 | Repo + kit | Terminal, Claude Code | — | Empty repo with the kit installed | Kit loads (`/` lists the skills) |
| 1 | Brainstorm → scope | Claude chat → `/product-brief` | Opus | `docs/product/brief.md`, `features.md`, `design-brief.md` | Every MVP feature has an ID, a screen, and acceptance notes |
| 2 | Design | Claude Design | — | `design/` (handoff bundle + HTML export) | Every MVP screen designed in all its states; tokens defined |
| 3 | Architecture | `/architecture` | Opus | `docs/architecture.md`, `docs/decisions.md` | Every MVP feature traces to components and entities; NFRs have numbers |
| 4 | Walking skeleton | `/skeleton` | Opus | Running slice, scripts, CI | Every script passes; CI green; slice shows seeded data |
| 5 | Configure kit | `/customize-kit` + GitHub settings | Opus | Filled `kit.json`, `CLAUDE.md`, agents | Smoke tests pass; branch protected |
| 6 | Plan the build | `/milestones` → `/new-task … M1` | Opus | `docs/tasklist.md`, M1 task files | Coverage 100%; M1 tasks reviewed and `Ready` |
| 7 | Build | `/next-task`, later `/plan-batch` + dispatch | Opus / Sonnet | PRs | M1 demo works; repeat 6–7 per milestone |

Stages 1–3 are where most rework is prevented. An hour spent on scope and data model saves several hours of tasks rebuilt against changed assumptions.

## Where are you now?

| Your situation | Start at |
|---|---|
| Just an idea | Stage 0 |
| Brainstormed in chat, nothing written down | Stage 0, then Stage 1 using the extraction prompt |
| **Brainstormed and design nearly finished, no task list** | **The fast path at the end of this guide** |
| Design done and exported, no architecture | Stage 3 (run `/product-brief` first if `features.md` doesn't exist) |
| Architecture written, no code | Stage 4 |
| Code exists, no tasks | Stage 5, then 6 |

---

## Stage 0: Repo and kit (about 15 minutes)

```powershell
mkdir C:\dev\my-app; cd C:\dev\my-app
git init -b main
gh repo create my-app --private --source . --remote origin

# Copy files directly from your extracted tools path
robocopy "C:\Development\tools\claude-code-starter-kit-v2" . /E /XF README.md USER-GUIDE.md WORKFLOW.md CHANGELOG.md KICKOFF.md
New-Item -ItemType Directory -Force docs\claude-kit | Out-Null
Copy-Item "C:\Development\tools\claude-code-starter-kit-v2\*.md" docs\claude-kit\ -Exclude CLAUDE.md

git add -A; git commit -m "chore: add Claude Code starter kit"; git push -u origin main

```

Start `claude` in the folder, accept the trust prompt, and type `/` to confirm `product-brief`, `architecture`, `skeleton`, and `milestones` appear. The hooks do nothing until `/customize-kit` fills `kit.json`, so they won't get in the way of early stages.

Set up branch protection after Stage 4, not now. Stages 0–3 commit docs straight to `main`.

## Stage 1: Brainstorm → scope (30–90 minutes)

### 1a. Brainstorm in Claude chat

Brainstorm freely. Before you finish, ask for an extraction, so nothing said in the chat is lost:

```text
Summarize this brainstorm as a Markdown document titled "Brainstorm notes" with these sections:
1. Problem and who it's for (including how they cope today)
2. Every feature idea mentioned, one bullet each, including ones we dismissed (mark those DISMISSED with the reason)
3. Screens or views we talked about
4. Data we'd store (things and their properties)
5. Constraints mentioned: budget, devices, hosting, offline, imports, deadlines
6. Decisions already made, and open questions
Don't invent anything we didn't discuss. Mark guesses as GUESS.
```

Save the result as `docs/product/brainstorm.md` and commit it.

### 1b. Turn it into scope in Claude Code

```text
/model opus
/product-brief docs/product/brainstorm.md
```

It asks up to 8 gap questions in one batch (MVP cut, success targets, constraints), then writes:

- `docs/product/brief.md`: problem, users, measurable goals, non-goals, constraints
- `docs/product/features.md`: `F-01…` features with MVP / Next / Later priority; `S-01…` screen inventory with the states to design; rough entities; cut list
- `docs/product/design-brief.md`: a ready-to-paste prompt for Claude Design

**Your review, about 15 minutes:**

1. Is the MVP the smallest set that replaces your current workaround?
2. Does every MVP feature have 2–3 observable acceptance notes?
3. Does every screen list its states?

Edit freely, then commit (`docs: product brief and features`).

## Stage 2: Design in Claude Design (2–6 hours, spread out)

1. **Start a project and paste `docs/product/design-brief.md`.** It asks for the design system first, then the screens, using the `S-01…` IDs as screen names. Names you use during the design conversation carry through to the handoff, so this pays off later.
2. **Work in this order:**
   1. Design system: palette, type scale, spacing, core components. Light and dark if you want both.
   2. The main flow's screens, end to end.
   3. Remaining MVP screens.
   4. States for every screen: empty, loading, error, plus long and short content.
   5. Phone and desktop layouts.
3. **Review pass.** Before you finish, ask:

   ```text
   Review this design against the screen inventory and states below. For each screen ID, list: missing states,
   inconsistent components or tokens, touch targets under 44 px, text that would truncate with long content,
   and any feature from the list that has no place in the UI. Table output, most important first.
   [paste the Screen inventory table and the MVP rows of the Feature list from features.md]
   ```

   Fix what matters, and repeat until the review comes back clean.
4. **Hand off.**
   - From the **Export** menu, choose the handoff to Claude Code. It packages the design and its intent for Claude Code to read.
   - Also export the HTML bundle.
   - Save both under `design/`, e.g. `design/handoff/` and `design/export/`. Unzip any downloaded archives.
   - Commit (`design: MVP handoff`).
   
   Menu labels change during the research preview. What matters is that the bundle and the HTML end up in `design/` in the repo, where every later stage reads them.

**Exit check:** every `S-xx` in `features.md` exists in the design with all its listed states. If you added screens during design, add them to `features.md` too.

## Stage 3: Architecture (45–90 minutes)

```text
/model opus
/architecture
```

It reads the brief, the features, and `design/`, infers the data model from what the screens display, then presents each key decision (stack, database, auth, hosting, testing) as 2–3 options with a recommendation. **You choose.** It then writes:

- `docs/architecture.md`: stack, ER diagram, entity tables, components, API, feature traceability, NFRs with numbers, testing strategy with seed data, walking-skeleton spec, risks
- `docs/decisions.md`: one row per decision, with the rejected alternatives

**Your review, about 20 minutes. This is the most valuable review in the whole kickoff.**

1. **Data model.** Does every entity and field match what the screens show? Is "stored vs. derived" explicit?
2. **Traceability.** No MVP feature maps to nothing.
3. **Risks.** Anything risky enough to spike before building (an import format, an external API)? Spike it now, in a throwaway branch.

Commit (`docs: architecture`).

## Stage 4: Walking skeleton (1–2 hours)

```text
/model opus
/skeleton
```

It plans first (**gate**), then builds the thinnest running system:

- framework scaffold;
- every script the kit needs (`typecheck`, `lint`, `test`, `test:e2e`, `build`, `db:migrate`, `db:seed`);
- one screen reading one seeded entity through the real data path;
- one unit test and one e2e smoke test;
- CI filled in;
- a README with dev setup.

It runs everything, then opens a PR.

Merge once CI is green. Then do USER-GUIDE §5.1 (branch protection) now that the `verify` check exists.

## Stage 5: Configure the kit (20–40 minutes)

```text
/customize-kit
```

With real scripts in place, it detects everything, fills `kit.json`, adds permission allow-rules, tailors the agents, and asks you to confirm 3–6 hard rules; the architecture doc already proposed candidates. Optionally do USER-GUIDE §5.2 (Claude GitHub App) for PR reviews. Merge the customization through a PR.

## Stage 6: Plan the build (30–60 minutes)

```text
/milestones
```

It shapes the MVP into 3–6 demoable milestones built from vertical slices, puts the riskiest work first, and checks that every MVP feature, screen, and entity lands in a task. **Gate**: approve the outline. It writes `docs/tasklist.md`.

Then convert **only the first milestone** into full task files:

```text
/new-task docs/tasklist.md M1
```

Review each task file. Rewrite any AC you couldn't check by looking at the app. Confirm the `autonomy` flags: early tasks are mostly `attended`, because they establish patterns. Set them to `Ready`, commit, and push.

Why one milestone at a time: specs written weeks ahead go stale as the code takes shape. Writing M2's specs once M1 is nearly done keeps file paths and patterns accurate.

## Stage 7: Build

Follow USER-GUIDE §7 (`/next-task`, attended) for M1. At the end of each milestone:

1. Run the milestone demo yourself (the "Demo at exit" line in `tasklist.md`).
2. Run a short retro (WORKFLOW.md) if you've done 10+ tasks.
3. `/new-task docs/tasklist.md M2`, review, `Ready`.
4. Once the metrics are on target, move eligible tasks to Level 2 (USER-GUIDE §8).

## After the MVP: adding features

| Change size | Path |
|---|---|
| Small (fits in 1–2 tasks, no new screens) | Add a row to `features.md` → `/new-task <description>` |
| Medium (new screen or entity) | `features.md` → design the screen in Claude Design and hand off to `design/` → `/new-task` per slice |
| Large (new area of the product) | Mini Stage 1–3: update the brief → design → `/architecture` (it amends the doc and adds decisions) → `/milestones Next` → `/new-task … M1` |

---

## Fast path: brainstorm done, design nearly finished, no task list

For a project where the design is almost done after brainstorming in chat, but there's nothing in a repo yet.

| Step | Do | Time |
|---|---|---|
| 1 | In the **brainstorm chat**, run the extraction prompt from Stage 1a. Save it as `docs/product/brainstorm.md` | 10 min |
| 2 | Stage 0: create the repo and install the kit. Commit the notes | 15 min |
| 3 | `/product-brief docs/product/brainstorm.md`. Answer the gap questions. Skip pasting `design-brief.md`, since your design exists, but keep it: its screen inventory is your checklist | 30–45 min |
| 4 | In **Claude Design**, run the Stage 2 review prompt with the new screen inventory. It shows exactly which screens and states are still missing. Finish those | varies |
| 5 | Hand off and export to `design/`; commit. Add any screens you designed but the inventory lacked to `features.md` | 15 min |
| 6 | Continue with Stage 3 (`/architecture`) and onward, as normal | — |

Steps 3–4 are the important ones. They turn "nearly finished" into a measurable state: a list of screen IDs and states, each either done or not.

## Kickoff anti-patterns

| Don't | Do instead |
|---|---|
| Go from chat straight to "build me the app" | Scope → design → architecture → skeleton → tasks; each stage feeds the next |
| Design before the MVP cut is decided | Cut first; design only MVP screens (park Next/Later) |
| Let the data model emerge from tasks | Settle it in `/architecture` from what the screens display |
| Write task files for the whole MVP up front | One milestone at a time |
| Start features before the skeleton's CI is green | Every later task relies on those checks |
| Keep the design only in Claude Design | Hand off and export to `design/`; agents can only read what's in the repo |
