---
id: TASK-000
title: <short imperative title>
status: Draft             # Draft | Ready | In progress | Review | Done | Blocked
depends_on: []            # e.g. [TASK-012, TASK-013]
size: S                   # S (<=3 files, one layer) | M (<=8 files, <=2 adjacent layers) | split if larger
model: sonnet             # implementation model; planning always uses Opus
autonomy: attended        # attended | unattended (see /new-task rules)
ui: false                 # true if any AC has a visible or interactive outcome
plan_status: none         # none | proposed | approved
planned_at_commit:        # set when the plan is written; used for the staleness check
---

# TASK-000 — <title>

## Goal

<1–2 sentences: the user-visible outcome. No implementation detail.>

## Context

- Feature / screen: F-<##> (`docs/01-product.md` › Feature index) · S-<##> (`docs/05-ui-design-brief.md` › Screen inventory)
- Architecture: `docs/02-architecture.md` § <section> · data model: `docs/03-data-model.md` § <section> · model: `docs/04-model.md` § <section>
- Design: `design/handoff/designs/<file>.dc.html` (board note <1a…>) · screenshot `design/handoff/screenshots/<file>.png`
- Decisions: D-<###>

## Acceptance criteria

Each item names an observable result and an expected value or state.

- [ ] AC-1: Given <state>, when <action>, then <result> (expected: <value>)
- [ ] AC-2:
- [ ] AC-3:

## Out of scope

- <Adjacent work a reasonable engineer might wrongly include>

## Files likely touched

- `<path>` — <why>

## Verification

- Automated: <test file / test name that must exist and pass>
- Manual: <step> → expected: <result>

## Plan

_Written by /plan-batch or /implement-task Phase 1. Approved by the user (plan_status: approved) before any code is written._

## Review log

_Filled by /implement-task. One line per round._

## Blocked

_Only if status is Blocked: what failed, what was tried, best hypothesis, decision needed._

## Metrics

- Verify rounds:
- Review rounds:
- First-pass AC FAILs:
- Plan revisions after approval:
