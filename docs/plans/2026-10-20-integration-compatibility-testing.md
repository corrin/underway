# Integration compatibility testing

Status: proposed, 2026-10-20. Priority: first. See [delivery order](README.md).

## Problem and existing foundation

`backend/tests/conftest.py` already uses MariaDB, and CI provisions MariaDB 11.
However, fixtures use `Base.metadata.create_all/drop_all`, bypassing Alembic.
Existing service/API mocks do not prove that actual SDK requests and provider
payloads still work together. Integrations use different transports: Todoist SDK,
Google discovery clients, Microsoft Graph SDK, and HTTPX calendar/OAuth calls.

There are concrete compatibility risks worth exposing: sync upserts omit account
identity in their lookup, missing tasks are hard-deleted, and Google/Outlook task
writes return success without implementing a remote write. Also verify the
deletion query's `DELETE ... RETURNING` against the supported database version.

## Design

- Retain fast unit tests. Add transport contract tests using real adapters and
  SDKs, replaying sanitized provider requests/responses at their HTTP boundary.
  Do not mock `get_tasks()` in tests intended to verify provider compatibility.
- Use pytest fixtures with a disposable MariaDB 11 service, initially matching
  CI; confirm deployed database/version before declaring parity. Run Alembic to
  head on an empty database. Use small seeded users, accounts, tasks and events.
  SQLite may support pure unit tests but is not the compatibility gate.
- Select replay tools after a small transport spike: evaluate VCR.py/pytest-recording
  for synchronous SDK transports and RESPX for HTTPX. Verify Graph and Todoist
  transports for the locked SDK versions; do not assume one interceptor covers
  every SDK. Prefer maintained tools to a custom protocol simulator.
- Store fixtures under `backend/tests/fixtures/providers/`, with provider/API and
  SDK versions, scenario, capture date, source (recorded or synthetic), and refresh
  instructions. Synthetic fixtures are useful but must not be labelled captures.
- Normal test runs are offline and fail on unexpected requests. Record mode is
  an explicit opt-in using dedicated sandbox accounts. Redact tokens, cookies,
  API keys, personal content, IDs and sensitive URLs consistently, including
  request bodies and query strings. Review fixture diffs before checking in.
- Replay exercises adapters into the real database and API where practical;
  assert normalized fields, persisted state, isolation and outbound request shape.
  A fake provider's state can be represented by scripted responses; a whole
  vendor database emulator is outside scope.

## Delivery slices

1. Database harness and one Todoist read contract: add a documented local service
   command (Compose or Testcontainers, choose one), readiness/cleanup, safe test
   URL validation and isolated database names. Apply Alembic and seed fixtures.
   Run the actual adapter and sync path against an explicitly synthetic fixture
   first if a sanitized recording is unavailable. Never record live traffic by
   default. Preserve existing tests while introducing the new fixture path.
2. Expand to Google Tasks, Outlook Tasks, Google Calendar and O365 Calendar.
   Cover pagination, empty versus failed fetches, two accounts with colliding
   remote IDs, completed/hidden/deleted tasks, date-only due dates, time zones,
   recurring/all-day events, malformed payloads and optional fields.
3. Cover OAuth expiry/rotation, revoked access, 401/403, 429 with Retry-After,
   timeouts and 5xx. Assert no destructive reconciliation after partial fetches
   and no successful remote-write claim from unsupported operations. Track bugs
   exposed by characterization and fix them separately before relying on them.
4. Add migration upgrade tests with representative pre-change rows, foreign-key
   and uniqueness checks, and isolation across users/accounts. Use unique DBs per
   worker or serialize these tests; never let parallel tests drop shared tables.
5. Add a required offline CI contract/migration job alongside current checks.
   Document fixture refresh and make sandbox smoke tests separately opt-in.
   Review fixtures on SDK/API upgrades; replay alone cannot detect vendor drift.

## Acceptance and validation

- One command runs the offline contract suite from an empty disposable DB.
- Real locked SDKs parse fixture payloads, emit expected requests and persist
  expected values through our sync/API paths; unexpected network calls fail.
- Alembic creates the tested schema; upgrade tests retain seeded data.
- Tests prove account/user isolation and distinguish full, partial and failed
  fetches. Known unsupported writes are visible as unsupported.
- Committed fixtures contain no credentials or personal account data.
- Existing backend checks and relevant browser flows continue to pass. CI does
  not require vendor credentials; optional sandbox checks report separately.

## Limits and decisions

This provides reproducibility and regression coverage, not a guarantee that a
vendor has not changed. Decide the deployed DB version and best replay tooling
in slice 1. Keep any temporary legacy metadata fixtures clearly separated and
retire them once migration-backed fixtures support the existing suite.
