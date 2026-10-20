# Library-based scheduling

Status: proposed, 2026-10-20. Priority: third. This replaces the generation and
publishing approach in [the original Phase 5 draft](06-phase5-schedule.md).

## Two distinct scheduling needs

1. **Background execution:** replace `task_sync_loop.py` and
   `token_refresh.py` sleep loops, started by every FastAPI lifespan, with a
   maintained job scheduler and a separately deployed worker.
2. **Time planning:** turn canonical tasks, actual time and calendar availability
   into useful work blocks. The README describes a rolling roughly seven-day
   horizon; the original draft only describes an LLM generating a daily schedule.

These need different libraries. Proposed choices are APScheduler for recurring
execution and OR-Tools CP-SAT for constraint-based planning, subject to short
Python 3.12/deployment spikes before pinning versions in Poetry. An LLM can help
interpret goals or explain choices; it must not determine constraint validity.

## A. Background worker

- Prefer a supported stable APScheduler release with asyncio integration. Verify
  its exact persistence/concurrency APIs and SQLAlchemy compatibility before
  implementation; do not mix examples from incompatible major versions.
  Compare Celery Beat + workers only if a broker/distributed queue is justified.
- Run one dedicated scheduler worker initially, outside Uvicorn workers. Register
  stable job IDs for task sync (15 minutes), token refresh (30 minutes) and OAuth
  state cleanup, preserving current startup execution where intentional. Expose
  run-once service functions to manual API calls and tests.
- Configure non-overlap, coalesced missed runs, grace periods, timeouts and clean
  shutdown through the library. Add database-backed exclusion/claiming where
  manual sync or overlapping deployments could touch the same account. Never
  assume a scheduler job store alone prevents concurrent execution.
- Use fresh database sessions per unit of work, bounded per-account concurrency,
  and transient-error retries respecting Retry-After. Revoked credentials require
  reauthentication, not endless retries. Split cleanup from token refresh so one
  failure does not prevent the other.
- Record last start/success, duration, failures and lag with job/account IDs and
  safe error summaries. Include worker health separately from HTTP health.
- Dispatch the canonical-data outbox after it exists, using atomic claims with
  expiry and retry state. Library job timing does not imply exactly-once remote
  delivery; the outbox provides application-level replay safety.

First slice may run after the testing foundation, before the canonical-data
project, because existing run-once sync/refresh services can be reused. Keep
legacy loops and the worker mutually exclusive; deployment must start exactly
one scheduling owner, with documented stop/rollback commands.

## B. Work planning

Depends on canonical tasks/time entries and calendar contract coverage. Begin
with a bounded preview, then expand to publication and automatic replanning.

- Inputs: active task UUIDs, duration estimates, due dates, priority, user timezone,
  working windows, slot-duration preference, existing busy events and a horizon.
  The README's 30-minute blocks and existing configurable slot duration differ;
  retain the setting initially and document the effective value. Require an
  estimate or a clearly displayed configurable default.
- Model discrete slots and optional task intervals with OR-Tools: no overlap,
  availability/busy exclusions, duration bounds and completed/archived exclusion
  are hard constraints. Define deadline policy explicitly; overdue/impossible
  work remains visible rather than silently breaking constraints. Initially
  schedule indivisible tasks; splitting/dependencies can follow measured need.
- Optimize priority and deadline pressure while penalizing unnecessary movement
  of existing blocks. Bound solver runtime and return feasible partial results
  with reasons for unscheduled tasks. Never label timeouts as an optimal result.
  Use timezone-aware boundaries, including DST and all-day busy events.
- Run CPU-bound solving off the async request loop. Persist `ScheduleRun` input
  revisions, policy/version and status, plus `ScheduledBlock` task reference,
  start/end, state and external event mapping. Planned blocks remain distinct
  from actual `TimeEntry` records.
- If availability fetch fails or is incomplete, mark the preview incomplete and
  block publishing for the affected calendar range. Do not treat outages as
  free time. Revalidate availability and input revisions before publishing.
- Publish only to a selected dedicated app calendar. Track ownership and stable
  operation IDs. Never overwrite unrelated events. Current providers expose
  list/create/delete, not update: add and contract-test capabilities before using
  update, or define recoverable replacement behavior explicitly.
- Publish/replan through the durable outbox. Reconcile timeout-after-create and
  partial batch failure to avoid duplicates. Respect manual moves/locks of app
  blocks. Expose preview, publish and retry status in API/UI. Start with manual
  publication; automatic replanning comes after these safety properties pass.

## Delivery slices and gates

1. Library spikes and recorded decision: supported versions, license, async/process
   model, startup/shutdown, persistence and deployment footprint. Demonstrate a
   nonoverlapping periodic job and a bounded solver fixture without cloud calls.
2. Replace loops with the worker. Test startup, missed runs, shutdown, long-running
   tasks, transient failures and duplicate worker/manual triggers using controlled
   time rather than real 15-minute sleeps. Prove requests stay responsive.
3. Preview-only one-day planning with canonical data, then seven-day support.
   Test busy exclusions, impossible loads, no tasks, missing estimates, deadlines,
   DST, solver timeout and deterministic tie-breaking with fixed inputs.
4. Persist runs/blocks and add a schedule preview/timeline, with unscheduled-task
   explanations and stale-preview handling. Use existing phase-5 UI ideas without
   its LLM-generated slot contract.
5. Add dedicated-calendar publication and reconciliation. Contract-test each
   supported provider, repeated publish, remote manual edits, partial failure,
   create timeout and safe cancellation. Add a browser preview/publish flow.
6. Enable bounded/coalesced replanning on task/time-entry changes and periodic
   availability refresh. Define locked/near-term block policy first. Add a
   disable switch for scheduling/publication and operational recovery notes.

## Deferred scope

Full goal ranking, allocation targets and interval goals described in the README
need their own domain plan. First scheduling release uses explicit task priorities
and estimates; it does not claim to implement that complete decision engine.
Distributed workers, recurrence inference and LLM-derived priorities are deferred
until the simpler measured workflow justifies them.
