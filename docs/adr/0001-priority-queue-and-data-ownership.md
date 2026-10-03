# ADR 0001: Priority queue and data ownership

Date: 2026-10-03

Status: Accepted

## Context

The app manages a priority queue of activities and chooses an activity for each
available calendar slot in the week. It uses the user's intentions and reports of
what actually happened to improve how their time is distributed.

Activities form a tree. Reported activity can be attached at any level and rolled
up to compare time distribution and progress against intentions. Activities such
as exercise and social catch-ups remain available after each occurrence. A node
can also have outstanding actions, occasional deadlines, and context needed to
pick up work after a long period of inactivity.

Sources such as Todoist already hold some of this information. Adding local
storage without defining its relationship to those sources would create a second
master and risk losing information when the local database is lost.

## Decision

**The app owns no master data. All durable user information must be persisted in
external systems.**

### Temporary implementation exception: intentions

The first queue implementation temporarily stores the intentions document locally,
behind the replaceable `IntentionsStore` interface. This is an explicit exception
to the target architecture, not a claim that local storage is synchronized.
It contains the activity tree, weekly minimums, cadence rules, permitted/preferred
hours, source bindings, editable effort estimates and firm-deadline overrides,
plus the selected calendar destination. Versioned JSON export/import preserves
stable node IDs and bindings; revisions reject stale concurrent edits.

Until an external intentions store replaces this adapter, recovery of intentions
requires an exported backup. Calendar and source reconnection alone cannot recover
that document. This exception must be removed before claiming the acceptance
criterion below is fully satisfied. No Google Sheets integration is introduced.

### Queue and activity implementation

- Todoist, Google Tasks and Microsoft To Do remain authoritative for imported
  tasks and their descriptions. Source identity includes provider, account and
  external task ID; moving a task between containers does not change that identity.
  Complete, successful account reads update the cache. Failed reads do not imply
  deletion. Source completion is written first, followed by a fresh read so a
  recurring task's next occurrence remains active.
- Published suggestions live in a dedicated Google or Microsoft calendar.
  Actual activity lives in a separate, non-busy calendar, with versioned event
  metadata carrying the report ID, node ID, local date, optional minutes, source
  reference and explicitly fulfilled cadence intentions. These records can be
  read after losing the local cache. Corrections replace the same report ID.
- The planner builds its queue and projected credits in memory, publishes the
  next seven days, then discards them. Published reservations never become actual
  activity automatically. Current/imminent and user-edited reservations are kept.
- Operational publication status and warnings are rebuildable local state.
  Provider failures leave confirmed reports intact. Partial publication is
  reconciled on retry using stable event identities and ownership metadata.

Existing local-only task creation and account/application settings remain legacy
gaps against this ADR; the queue does not consume local-only tasks or introduce
additional durable project context there.

This includes the activity tree, intentions, reported activity history, node
notes and context, outstanding actions, user preferences, and any mappings needed
to reconstruct their relationships. Information introduced through the app has
the same requirement as information imported from a source.

The local database may hold source caches, indexes, derived state, and clearly
identified pending synchronization operations. The priority queue and rollups
are derived from the externally persisted inputs. Calendar blocks express the
queue's current choices; their passage does not establish that an activity
actually happened.

For each stored data type, its design must identify:

- The external system and record that hold the authoritative information.
- The stable external identity, including the source account, used to link it to
  local records and related information.
- How source changes are imported and changes made through the app are written
  back, including conflict and failure handling.
- How the information and its relationships are recovered without the local
  database.

Source edits must be reflected in the local cache. Changes made through the app
must sync to the designated external home. A write that has not been acknowledged
by that system must remain visibly pending or failed; it must not be reported as
durably saved. Pending local operations are temporary synchronization state, not
an alternative authoritative store.

Queue adjustments are derived scheduling decisions. They do not implicitly
rewrite source task priorities, descriptions, or other user-authored information.

## Consequences

New persistent features must define their external home and synchronization
behavior before relying on local storage. This ADR does not choose a storage
encoding or assign all new information to Todoist; those choices require a
specific synchronization design.

Durable context must be recoverable independently of a chat context window.
Source renames, moves, completion, and deletion need explicit synchronization
semantics that preserve links to activity history. A missing record in a partial
or failed fetch is not evidence that the user deleted it.

This decision constrains incremental development of the existing app. It does
not introduce a project parking workflow or prescribe a new queue-scoring
algorithm. It records requirements, not a claim that the current implementation
already satisfies them.

## Acceptance criterion

After externally acknowledged writes, losing the local database and reconnecting
the external sources must allow the app to recover the durable user information
and relationships needed to rebuild the queue. Recovery must include intentions,
activity history, node context, outstanding actions, and preferences; it must not
depend on retained conversation context or an otherwise unique local record.
