# ui-verifier: cfb-model

Project section for `.claude/agents/ui-verifier.md`. The kit never ships or overwrites this file.

## Sign-in

None yet (`ui.auth` is null). When GitHub sign-in lands, the dev server needs a dev-only sign-in that `ui.auth.steps` can drive; it must never reach production.

## Data

The dev server started by `ui.startCommand` reads the database in `.env.local` (development, never production). Use only data already there or data the steps create; never delete or bulk-edit rows, and never run ingest, seed or migrate commands.

## Design sources

- The `Pass … .dc.html` boards in `design/handoff/designs/` win over older boards; their board notes are the spec. The boards are 100–300 KB: Grep for the board or frame name, then Read with offset/limit (the `largeFiles` hint), never whole.
- `docs/05-ui-design-brief.md` loses to the design unless it notes an override. Numbers and what they mean follow `docs/04-model.md`.

## Reference screenshots

- `design/handoff/screenshots/` names them `NN-<screen>-<desktop|mobile|tablet>.png`: desktop = 1440, mobile = 390, tablet = 768. Only This Week has a tablet reference (`28-this-week-tablet.png`).
- Compare numbers and copy against a reference only when the server runs on the seeded test DB (the fixture reproduces them, `docs/02-architecture.md` › Testing strategy). Against dev data, ignore data values.
- The references show the default dark theme.
