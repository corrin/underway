# Phase 2: Task Management — COMPLETED 2026-03-08

**Goal:** Port the full task management system: CRUD API, provider sync, drag-and-drop ordering, and the Vue task list page.

**Status:** All tasks complete. All quality gates passing. PR #10.

## What was built

### Backend
- **Task provider abstraction** (`aligned/providers/task_provider.py`) — ABC with `authenticate`, `get_tasks`, `update_task`, `update_task_status`, `get_ai_instructions`
- **Provider implementations:**
  - Todoist (`aligned/providers/todoist.py`) — full implementation with async HTTP
  - Google Tasks (`aligned/providers/google_tasks.py`) — uses `google-api-python-client` with typed stubs
  - Outlook (`aligned/providers/outlook_tasks.py`) — uses `msgraph-sdk` (Microsoft Graph `todo.lists` API)
- **Task manager** (`aligned/providers/task_manager.py`) — coordinator that instantiates providers
- **Task sync service** (`aligned/services/task_sync.py`) — content hash-based change detection (SHA256)
- **Task ViewSet** (`aligned/viewsets/tasks.py`) — full CRUD + custom actions: `by-list`, `move`, `reorder`, `sync`, `update-status`
- **Todoist auth routes** (`aligned/routes/todoist_auth.py`) — add/update/delete/test API keys
- **Token refresh** (`aligned/providers/token_refresh.py`) — background async loop for OAuth token refresh
- **O365 credentials** (`aligned/providers/o365_credentials.py`) — `TokenCredential` subclass for Microsoft Graph

### Frontend
- **Task board** (`views/TasksView.vue`) — three-column drag-and-drop layout (prioritized/unprioritized/completed)
- **Task card** (`components/TaskCard.vue`) — status toggle, priority badge, delete
- **Pinia store** (`stores/tasks.ts`) — reactive task state with fetch/move/reorder/sync actions
- **API client** (`api/tasks.ts`) — typed axios wrappers for all task endpoints
- **vuedraggable** — drag-and-drop between lists

### Type safety
- **Zero suppressions:** no `type: ignore`, no `noqa`, no per-file-ignores, no ruff rules disabled
- **Proper stubs:** `google-api-python-client-stubs` for Google API, `google.oauth2.credentials` stub for untyped constructor, `msgraph-sdk` has `py.typed`
- **Deleted local fastrest stubs** — upstream fastrest now has `py.typed`

### Tests
- 76 passing tests (unit + integration)
- Unit: task sync service with content hash detection
- Integration: full CRUD, by-list grouping, move/reorder, todoist auth endpoints, auth scoping

### API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/tasks` | List tasks (filterable) |
| POST | `/api/tasks` | Create task |
| GET | `/api/tasks/{pk}` | Get task details |
| PUT | `/api/tasks/{pk}` | Update task |
| PATCH | `/api/tasks/{pk}` | Partial update |
| DELETE | `/api/tasks/{pk}` | Delete task |
| GET | `/api/tasks/by-list` | Tasks grouped by list type |
| POST | `/api/tasks/move` | Move task between lists |
| POST | `/api/tasks/reorder` | Reorder within a list |
| POST | `/api/tasks/sync` | Sync from providers |
| POST | `/api/tasks/{pk}/update-status` | Update status + provider sync |

## Key decisions
- `HTTPException` raises instead of `JSONResponse` returns for error paths (avoids `type: ignore[return-value]`)
- `**kwargs: object` on `TokenCredential.get_token` override (satisfies both Azure interface and ruff ANN401)
- Content hash sync uses SHA256 of serialized task fields to detect changes
- Provider implementations are partial (Google/Outlook stubs for update methods) — sync reads work fully
