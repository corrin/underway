# Weekly priority queue

The app chooses an activity for each available slot over the next seven days.
Configure **Settings → Activity intentions**, select a connected Google or Microsoft
calendar account, add available hours and an activity tree, then enable publishing.
Slots can be 30, 60 or 120 minutes. Scheduling is disabled by default.

Use chat to bind source projects/lists or individual tasks to nodes, set preferred
hours or firm deadlines, and report actual activity. For example:

- “Friends should happen at least once every seven days.”
- “I spent about 90 minutes with friends yesterday.”
- “That catch-up was with Sam; correct the report to 60 minutes.”

Reports can attach to any node. Minutes roll up to ancestors, never down to
children. A duration can remain unknown: a qualifying occurrence still satisfies
a cadence rule but contributes no invented minutes. The sidebar shows percentages
of recorded time and progress against each weekly minimum. These percentages
describe recorded time, not all elapsed time.

## Selection rules

Weekly minimums use Monday–Sunday in the configured timezone. At each branch,
overdue cadence intentions take precedence, then the smallest fraction of a
weekly target achieved. An unmet descendant can raise its whole branch. Planning
credits allocations separately from actuals so one neglected branch does not
consume every slot. Ratios can exceed 100% to distribute spare capacity.

Preferred hours are soft: an out-of-window candidate receives a 0.25 penalty to
its target ratio. Available hours, busy calendar commitments and retained
reservations are hard constraints. Source priority, due date, recency and stable
identity break ties. A due date alone is not a firm deadline.

Firm deadlines reserve slots backwards, earliest deadline first, aiming for a
24-hour margin. Capacity is inspected through the latest deadline, even beyond
the visible week. Insufficient capacity or unknown effort produces a warning;
unknown effort receives a review slot rather than an invented guarantee.

`estimated_minutes` is a rough total effort budget for a finite action. Reported
minutes explicitly linked to that action reduce its remaining allocation. When
the estimate is exhausted but the source still says active, one review slot is
kept and a warning requests completion or a revised estimate. Chat can suggest an
estimate from source descriptions; save it on a node bound to that specific task.
Repeatable activities do not become completed tasks.

## Publication and recovery

The app creates **Underway - schedule** and **Underway - activity** calendars.
The former contains suggestions; the latter holds dated, non-busy actual reports.
The current block, the next 30 minutes, and suggestions moved or renamed by the
user are retained. Other owned future suggestions can be updated or removed.
Unowned events are never edited. Calendar time passing does not count as activity.

Refresh runs every 15 minutes and after intention edits, activity reports and
source-task edits. A failed source read prevents publication from that snapshot.
An interrupted publication can be partial; retry reconciles it. Disabling
scheduling stops regeneration and leaves existing calendar entries in place.

The temporary local intentions store is the exception documented in
[ADR 0001](adr/0001-priority-queue-and-data-ownership.md). **Export a backup after
changing intentions.** To recover, reconnect the same external accounts, import
the backup, review the destination and enable scheduling. Stable node/report/task
IDs preserve links. Import is initially disabled to allow review. Source tasks
and actual reports are fetched externally; the priority queue itself is rebuilt.
Existing Microsoft connections may need reconnection for the Tasks.ReadWrite scope.

## API

All endpoints require the current user's authentication:

| Endpoint | Purpose |
| --- | --- |
| `GET /api/intentions` | Export the versioned intentions document |
| `PUT /api/intentions` | Validate/import a full document with the current revision; regenerate |
| `GET /api/schedule` | Published slots, actual reports, rollups, warnings and publication status |
| `POST /api/schedule/rebuild` | Refresh inputs and reconcile suggestions |
| `POST /api/activity` | Save a report; reuse its ID on retries |
| `PUT /api/activity/{id}` | Explicitly correct that report |

A source binding uses `provider` (`todoist`, `google_tasks` or `outlook`),
`account`, `container_id` and optional `task_id`. A task binding includes source
descendants; individual bindings override project bindings. Unbound tasks are
not scheduled; unbound firm deadlines produce warnings. Reports remain readable
if a source task disappears. Node IDs should be retained when renaming/reparenting.

Apply migration `8a13b64720ef` using the normal deployment process before starting
this version. Provider contract tests use mocked APIs; live account authorization
and provider acceptance still need verification when enabling the feature.
