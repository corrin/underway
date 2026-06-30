# Settings External-Account Controls — Design

**Date:** 2026-06-30
**Branch:** feat/wire-task-sync
**Status:** Approved (brainstorming)

## Problem

The Settings → External Accounts section offers only one-way controls:

- **Re-auth:** a "Needs re-auth" badge with no action button. Re-authing is only
  possible by clicking the generic "Connect Google Calendar" button at the bottom of
  the page, which is not discoverable as the fix for a flagged account.
- **Tasks:** a "Use for tasks" button that only *enables* (`use_for_tasks = True`).
  No way to turn it off.
- **Calendar:** auto-enabled on every Google connect (`use_for_calendar = True` in the
  OAuth callback). No explicit enable/disable control — only a "Calendar" badge.

Net effect: connecting turns calendar on, the button turns tasks on, and nothing turns
either back off. There is no per-row re-auth action.

This also blocks e2e testing of Google Tasks sync: the test fixture requires a Google
account with `use_for_tasks=True` and `needs_reauth=False`, and the only path to that
state today is the non-obvious generic connect button.

## Goals

1. Per-account **Re-authenticate** action, shown when the account needs re-auth.
2. Calendar and Tasks become **on↔off** controls per account (enable *and* disable).
3. Disabling a source stops future syncs but leaves already-synced rows in place.
4. The new "Use for tasks" toggle becomes the setup path for the Google Tasks e2e test.

## Non-Goals

- Removing/deleting an external account entirely (separate concern).
- Changing sync internals beyond what the `use_for_*` flags already gate.
- Reworking the bottom "Connect …" buttons, which remain for adding *new* accounts.

## Disable Semantics (decided)

Disabling a source sets its `use_for_*` flag to `False`, which the existing sync queries
already honor (`calendar.py` filters `use_for_calendar.is_(True)`; task sync filters
`use_for_tasks.is_(True)`). This **stops future syncs** for that source.

**Already-synced rows are kept**, not deleted. Tradeoff accepted: kept rows become
frozen — no further upstream edits or delete-reconciliation reach them until the source
is re-enabled, so they can go stale. Chosen for the lower blast radius.

Calendar behaves symmetrically with tasks.

## Architecture

### Backend — single toggle action (Approach B)

Replace the enable-only `use-for-tasks` action on `ExternalAccountViewSet`
(`backend/underway/viewsets/external_accounts.py`) with one parameterized action:

```
POST /api/external-accounts/{pk}/source
body: { "source": "tasks" | "calendar", "enabled": true | false }
```

A shared private helper `_set_source(account, source, enabled)`:

- Flips the matching `use_for_*` flag.
- **On enable:** promote the account to primary for that source via the existing
  `ExternalAccount.set_as_primary(...)` (which clears the flag on sibling accounts).
- **On disable:** if the account was the primary for that source, clear its
  `is_primary_*` flag and promote another still-enabled account of the same source to
  primary if one exists; otherwise leave no primary.

Validation / error paths preserved from the current action:
- Invalid UUID → 400.
- Account not found / not owned by current user → 404.
- Invalid `source` value → 400.

The viewset stays a `ReadOnlyModelViewSet`; the only mutation is through this explicit
action (no writable serializer, so token fields are never exposed).

### Frontend — per-row controls (`frontend/src/views/SettingsView.vue`)

Each account row renders state + an action button per source:

- `Calendar: on/off` with a button that flips between **Disable calendar** /
  **Use for calendar**.
- `Tasks: on/off` with a button that flips between **Stop using for tasks** /
  **Use for tasks**.
- **Re-authenticate** button, rendered only when `account.needs_reauth`, calling the
  existing `connectGoogle()` / `connectO365()` based on `account.provider`.

All four source buttons call one `setSource(accountId, source, enabled)` that POSTs to
`/external-accounts/{id}/source` then calls `loadAccounts()` to refresh. A per-row
busy state disables the buttons while a request is in flight.

The bottom "Connect Google Calendar" / "Connect Microsoft 365" buttons are unchanged
(add new accounts).

### Re-auth wiring (no new backend)

The Re-authenticate button reuses the OAuth initiate flow. That flow already forces
`prompt=consent`, re-grants all scopes (including Tasks), upserts the same account, and
sets `needs_reauth=False` in `handle_google_oauth_callback`.

**Known nuance (accepted):** that same callback forces `use_for_calendar=True`, so
re-authenticating re-enables calendar even if it had been toggled off. Left as-is —
re-consenting implies the account should be active.

## Testing

### Backend unit tests (`source` endpoint)
- Enable tasks → `use_for_tasks=True`, account becomes primary tasks.
- Disable tasks → `use_for_tasks=False`; primary reassigned to another enabled account
  if present, else no primary.
- Same pair for calendar.
- Invalid `source` → 400; bad UUID → 400; other user's account → 404.

### E2E (Playwright, `backend/tests/e2e`)
- New test: in Settings, toggle "Use for tasks" on for the connected Google account and
  assert the account becomes task-eligible (badge/state reflects it). This is also the
  setup path for the existing Google Tasks sync test.
- Per project rule, the previously-manual UX gap is now an automated assertion.

## Affected Files

- `backend/underway/viewsets/external_accounts.py` — replace action with `source` toggle + `_set_source` helper.
- `frontend/src/views/SettingsView.vue` — per-row toggle buttons + re-auth button + `setSource()`.
- `backend/tests/` — unit tests for the toggle endpoint.
- `backend/tests/e2e/test_tasks.py` (or sibling) — Settings toggle e2e.

## Open Risks

- Primary reassignment on disable is the trickiest logic; covered by unit tests.
- Re-auth re-enabling calendar is intentional but documented so it isn't mistaken for a bug.
