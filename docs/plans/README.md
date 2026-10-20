# Current delivery plan

Status: proposed, 2026-10-20. Planning only; implementation has not started.

The numbered phase documents describe the original migration, not a verified
backlog of remaining work. Keep them as design history. Current code and tests
take precedence over their completion claims. The settings/account-controls
design in `../superpowers/specs/2026-06-30-settings-account-controls-design.md`
remains relevant and should be reconciled when changing account lifecycle.

## Recommended order

| Order | Plan | Why now | Dependency |
| --- | --- | --- | --- |
| 1 | [Integration compatibility testing](2026-10-20-integration-compatibility-testing.md) | Establish a trustworthy baseline before changing sync and persistence | None |
| 2 | [Owned tasks and time entries](2026-10-20-owned-tasks-and-time-entries.md) | Make our data durable independently of providers; supply actual activity to scheduling | Testing foundation |
| 3 | [Library-based scheduling](2026-10-20-library-based-scheduling.md) | Run reliable background jobs and schedule against canonical tasks and actual time | Testing foundation; canonical data before calendar publishing |

**Pick next:** the first testing slice: an isolated MariaDB database built with
Alembic, plus one sanitized Todoist transport replay through the real adapter
and sync service. It is small enough to review and establishes the pattern for
the other integrations. Expand coverage to Google and Microsoft before changing
their sync behavior. Characterize current behavior, but do not enshrine known
data-loss bugs or stubbed writes as desired contracts.

Background job replacement can follow that first testing slice if polling is an
immediate operational problem. Otherwise finish the data model before expanding
automation. Keep changes in separate reviewable increments with the gates in
each plan; do not combine all three into a rewrite.

## Existing drafts to retain and reconcile

- Phases 0–3 remain historical context; Phase 2 is marked complete, but its
  provider-write claims need verification against the implementation.
- [Phase 4 calendar](05-phase4-calendar.md) remains useful for calendar/OAuth
  behavior and UI. Calendar code and tests already exist; audit remaining gaps
  instead of replaying its steps wholesale.
- [Phase 5 schedule](06-phase5-schedule.md) retains useful preview/timeline ideas.
  The new scheduling plan supersedes its LLM slot-generation and direct publish
  design. A valid schedule must be enforced by constraints and published safely.
- Existing CI/deployment and settings plans remain separate workstreams. These
  plans neither mark them complete nor remove their requirements.

## Working assumptions

"Mini database" means a disposable instance of our production database family,
seeded with small realistic datasets, plus replayed external API responses. It
does not mean replacing MariaDB with SQLite or reproducing entire vendor systems.
"Scheduler" covers both periodic background execution and planning work into time
slots. Libraries for these serve different purposes; the scheduling plan treats
them separately.

Deferred product choices are explicit in the individual plans. No live-account
recording, production data migration, or calendar publishing is part of this
documentation change.
