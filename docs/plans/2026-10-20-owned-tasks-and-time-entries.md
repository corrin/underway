# Own task and time-entry master data

Status: proposed, 2026-10-20. Priority: second; depends on the
[compatibility testing foundation](2026-10-20-integration-compatibility-testing.md).

## Problem

`Task` already has a local UUID and supports local creation, but also embeds
provider identity, content hash and sync timestamps. `task_sync.py` overwrites
fields from providers and hard-deletes rows absent from a fetch. That is a cache
model rather than durable master data. There is no time-entry model in the
current backend. A disconnected provider must not erase our tasks or work history.

## Proposed ownership and schema

- `Task` is canonical: stable UUID, user, title, description, status, due value,
  priority, local hierarchy, ordering, estimate, revision, timestamps and archive
  state. Represent date-only deadlines separately from instants/time zones.
  Provider fields move out of the canonical record.
- `TaskExternalLink` maps a task to an `ExternalAccount` and remote container/task
  identity. Enforce uniqueness on account + remote identity (including container
  where provider IDs require it). Store remote version/ETag, last acknowledged
  snapshot, sync cursor/status, tombstone and last error. Use immutable account
  IDs rather than email as identity. Account ownership must match task ownership.
- `TimeEntry` records actual activity: UUID, user, optional task, start/end UTC,
  description, source, revision and audit timestamps. Entries may be unassigned;
  a completed task need not have time logged and logging time does not complete
  a task. Calendar plans are not automatically actual time entries.
- First release supports completed intervals only; require end > start and
  derive duration. Store reporting time zone, use half-open intervals and split
  totals at local day/week boundaries. Flag overlaps rather than silently double
  counting; settle whether overlaps are allowed before the reporting UI ships.
  Timers, external time-tracking adapters and billing are deferred.
- Durable outbox operations are committed in the same transaction as canonical
  changes. Record operation key, target link, revision, attempts, next attempt,
  result and error. Provider calls occur outside the canonical transaction.

## Reconciliation rules

Our database is the record served to UI, chat and scheduling. External changes
are inputs reconciled against it, not an unconditional overwrite. First release
imports new remote tasks and accepts remote edits only when the local field has
not changed since the acknowledged snapshot. Local-only changes are queued for
supported write-back. Concurrent edits become visible conflicts; retain local
data until resolved, then advance the baseline. Use revisions to reject stale
local edits and prevent an old retry overwriting a newer change.

Do not infer deletion from a failed/partial fetch or from an active-only list
that omits completed tasks. Require explicit deletion evidence or a verified
complete snapshot with defined semantics. Remote deletion marks the link and
retains the local task. Local deletion archives the task; remote deletion is a
separate explicit operation. Unlinking an account preserves tasks/time entries,
removes credentials, and stops/cancels queued work for that account.

Retries are at least once. Use vendor idempotency keys when available; otherwise
reconcile ambiguous outcomes before retrying a create. Read-only/unsupported
provider operations remain explicit; the Google/Outlook stubs must never be
presented as successful synchronization. Do not automatically merge two tasks
because their titles match or export every local task to every provider.

## Delivery slices

1. Add canonical/link schema and Alembic backfill. Preserve every existing task
   UUID, user, list position and relationship. Map provider/email rows to exactly
   one account; report ambiguous/orphan mappings for review, never guess. Local
   tasks receive no external link. Verify row counts and uniqueness on a seeded
   migration and a dry-run inventory before enabling constraints.
2. Route all task mutations (CRUD, board, status, chat) through one service.
   Commit local changes independently of provider availability and expose sync
   state in API/UI. Keep existing API fields temporarily as a documented
   compatibility projection; add canonical/link fields before removing old ones.
3. Implement inbound reconciliation, conflicts, tombstones and transactional
   outbox. Start with one supported Todoist operation, then expand by capability.
   Keep manual dispatch available until the scheduler worker exists. Include
   account-scoped identity in every lookup and authorization check.
4. Add `/api/time-entries` CRUD and task/date filtering, with ownership validation,
   client idempotency keys for duplicate submissions, revision checks and a small
   manual logging/editing UI. Expose the same validated service to chat tools;
   require an explicit reported interval rather than inventing elapsed time.
5. Cut reads over to canonical records, reconcile API/frontend types and remove
   legacy provider columns only after a separate verified migration. Preserve
   provenance and offer conflict/retry status without requiring provider access
   to view or edit local data.

## Acceptance and validation

- Tasks can be created, edited and completed with no external accounts or during
  an outage; reconnecting does not lose pending edits or duplicate tasks.
- Same remote ID in two accounts remains distinct. Every new link and time-entry
  API rejects cross-user access and cross-user task references.
- Replaying a sync/outbox item is harmless; conflict, crash-after-send and stale
  retry scenarios preserve local data and report ambiguous delivery honestly.
- Account unlink and remote deletion preserve tasks and time history. Partial
  snapshots do not delete data. Archive behavior preserves time-entry references.
- Migration tests retain UUIDs and data; replay tests cover supported inbound
  and outbound operations. Browser tests cover offline local edit, sync failure
  visibility, manual time logging and editing across a timezone boundary.
- DB backup/dry-run and additive rollout precede any production cutover. Once
  new canonical writes exist, rollback must preserve them; do not blindly restore
  the old schema or resume destructive legacy sync. Pause sync for recovery.

## Scope decisions

Confirm whether eventual multi-provider linking is needed; support the link
table shape now but defer automatic merging. Goals/time-allocation policies are
future domain work, not implicitly supplied by this data migration.
