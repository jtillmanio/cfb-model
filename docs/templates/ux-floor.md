# UX floor: {{PROJECT_NAME}}

_Template. The minimum every UI task meets, whatever its screen. Map it as the **UX floor** role in the "Project docs" table in `CLAUDE.md`. `/new-task` adds an acceptance criterion pointing here to every task with `ui: true`; spec-reviewer and ui-verifier check it. Adjust the numbers to the design; delete what doesn't apply._

A screen is not done until all of these hold.

## States

- Every screen has its **empty**, **loading**, and **error** states drawn and built, plus any others its data can reach (offline, rate-limited, partial data).
- Empty: one primary action that gets the user out of it.
- Loading: a skeleton at the loaded size, so nothing jumps when data arrives.
- Error: says what happened and what the user can do; it isn't styled as destructive unless something was destroyed.
- An unavailable action says why, next to it, rather than being silently disabled.

## Contrast

- Body text at least 4.5:1 against its background, large text 3:1, in every theme the app has.
- Control outlines and focus indicators at least 3:1.
- Meaning never carried by colour alone: a status has a glyph or text too.

## Targets and controls

- Primary touch targets at least {{44}} px; nothing interactive under {{24}} px.
- Every control is a real `<button>` or `<a href>` (or the platform's equivalent) with an accessible name.
- Everything reachable by keyboard, in a sensible order, with a visible focus ring. A dialog or sheet returns focus to what opened it.
- Hover-only affordances have a touch route.

## Motion

- With `prefers-reduced-motion`, animations are off or reduced to fades; nothing essential depends on motion.

## Widths to screenshot

- Each width in `ui.viewports` in `.claude/kit.json` (default phone 390, tablet 768, desktop 1440), in each theme the app has.
- No horizontal scroll at any of them.

## Numbers in the design

Figures in mockups and screenshots are sample data. Acceptance checks assert relationships or their own fixtures, never a number copied from the design.
