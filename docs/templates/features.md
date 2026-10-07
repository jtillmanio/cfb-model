# Features: {{PROJECT_NAME}}

_Source of truth for scope. `/milestones` checks that every MVP feature lands in at least one task._

## Feature list

| ID | Feature | User story | Priority | Screens | Data touched | Acceptance notes |
|----|---------|------------|----------|---------|--------------|------------------|
| F-01 | {{name}} | As {{user}}, I want {{...}} so that {{...}} | MVP | S-01 | {{entities}} | {{2-3 observable outcomes; become ACs later}} |
| F-02 | | | Next | | | |
| F-03 | | | Later | | | |

Priority: **MVP** (launch blocker) · **Next** (first release after MVP) · **Later** (parked; not designed or built).

## Screen inventory

| ID | Screen | Purpose | Features | States to design |
|----|--------|---------|----------|------------------|
| S-01 | {{e.g. Home / dashboard}} | {{...}} | F-01, F-02 | default, empty, loading, error |

## Entities (rough)

| Entity | Key fields | Relationships | Notes |
|--------|-----------|---------------|-------|
| {{e.g. Book}} | {{title, author, status}} | {{belongs to Series}} | {{...}} |

## Cut list

_Ideas from brainstorming deliberately left out, so they don't creep back in unannounced._

- {{idea}}: {{why it's cut}}
