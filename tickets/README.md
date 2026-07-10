# Tickets

Local, git-tracked work items. One markdown file per ticket: `DANDER-<n>-<slug>.md`.
The **Product agent** creates them; **Design** fills the Design section; **Code** implements;
**PR-Review** appends to the Review Log and flips status. The `feature` workflow drives this loop.

## Lifecycle (the `status` field)

`open` → `in-design` → `in-code` → `in-review` → (`done` | back to `in-code` with an addendum)

- **open** — created by Product, has acceptance criteria, no design yet.
- **in-design** — a Design agent is producing the technical approach.
- **in-code** — a Code agent is implementing against the design.
- **in-review** — implementation done, awaiting PR-Review.
- **done** — passed review against acceptance criteria + steering. Terminal.

On a review FAIL, PR-Review appends an **Addendum** under Review Log and sets status back to
`in-code`; the Code agent addresses it. Repeat until PASS (workflow caps the rounds).

## Frontmatter (required)

```yaml
---
id: DANDER-1
title: Short imperative title
status: open            # open | in-design | in-code | in-review | done
component: python       # python | sql | terraform | docs  (selects the code agent)
epic: security-module   # optional grouping
depends_on: []          # list of ticket ids that must be done first
created: 2026-07-09
---
```

## Body sections (in order)

1. **Context** — why this exists; link to `steering/00-project-overview.md` where relevant.
2. **Acceptance Criteria** — checklist; the definition of done PR-Review checks against.
3. **Design** — filled by the Design agent (approach, interfaces, files to touch).
4. **Implementation Notes** — filled by the Code agent (what was built, decisions, deviations).
5. **Review Log** — append-only; PR-Review adds `PASS`/`FAIL` entries + addenda.

See `TEMPLATE.md` for the skeleton to copy.
