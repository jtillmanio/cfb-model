# Owner checklist

_Template. `/customize-kit` (or a follow-up placement, with your OK) creates the checklist from it at the path the **Owner checklist** row of the "Project docs" table in `CLAUDE.md` names._

What only the owner can do, and follow-ups waiting for the owner's approval. Claude adds items and never ticks an action; the owner ticks them. Each item names where it came from.

## Actions

Things only you can do: secrets, dashboard and hosting settings, purchases, production data.

- [ ] <action> (from TASK-### , PR #n)

## Approvals

Follow-ups that change a planning doc, or decisions to record, that Claude makes only with your yes. Tick one (or say "approve <item>" in a session) and the session you told, or the next `/track-follow-ups` run, makes the change and adds where it went.

- [ ] <change to make> → <path> § <section> (from TASK-###, PR #n)

## Done

- [x] <item> → <where it went> (PR #n)
