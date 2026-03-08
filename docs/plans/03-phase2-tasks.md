# Phase 2: Task Management

## Goal

Port the full task management system: CRUD API, provider sync, drag-and-drop ordering, and the Vue task list page.

## Source Files

| Original | New |
|----------|-----|
| `tasks/task_routes.py` | `aligned/viewsets/tasks.py` |
| `tasks/task_manager.py` | `aligned/providers/task_manager.py` |
| `tasks/task_provider.py` | `aligned/providers/task_provider.py` |
| `tasks/todoist_provider.py` | `aligned/providers/todoist.py` |
| `tasks/google_task_provider.py` | `aligned/providers/google_tasks.py` |
| `tasks/outlook_task_provider.py` | `aligned/providers/outlook_tasks.py` |
| `tasks/todoist_routes.py` | `aligned/viewsets/todoist_auth.py` |
| `tasks/token_refresh.py` | `aligned/providers/token_refresh.py` |
| `templates/tasks.html` | `frontend/src/views/TasksView.vue` |
| `static/js/tasks.js` | `frontend/src/components/TaskList.vue` etc. |

## Steps

### 2.0 Test Auth Bypass for Playwright

Add a dev/test-only login endpoint that creates a valid session without going through Google OAuth. Google actively blocks automated login, so this is the standard pattern for E2E testing with OAuth providers.

```python
# aligned/viewsets/auth.py — only registered when TESTING/DEBUG

if settings.TESTING:
    @router.post("/api/auth/test-login")
    async def test_login(request):
        """Bypass Google OAuth for Playwright tests. Only exists in test env."""
        # 1. Accept an email directly (no Google token verification)
        # 2. Find or create User by email
        # 3. Return JWT access token (same as real login)
```

Key requirements:
- **Route must not exist in production** — conditionally register based on `settings.TESTING` so it's not just guarded but completely absent
- Returns a real JWT so all subsequent API calls work identically to a real login
- Playwright tests call this endpoint in `beforeEach` to get a token, then set it in the browser context
- Add a Playwright auth fixture that handles this, reusable across all E2E tests:

```typescript
// e2e/fixtures/auth.ts
import { test as base } from '@playwright/test'

export const test = base.extend({
  authenticatedPage: async ({ page }, use) => {
    const res = await page.request.post('/api/auth/test-login', {
      data: { email: 'test@example.com' }
    })
    const { token } = await res.json()
    await page.evaluate(t => localStorage.setItem('token', t), token)
    await use(page)
  },
})
```

This unblocks all E2E tests in Phase 2+ that require an authenticated user.

### 2.1 Task Serializers

```python
# aligned/serializers/task.py

class TaskSerializer(ModelSerializer):
    class Meta:
        model = Task
        fields = [
            "id", "user_id", "task_user_email", "provider", "provider_task_id",
            "title", "description", "status", "due_date", "priority",
            "project_id", "project_name", "parent_id", "section_id",
            "list_type", "position", "last_synced",
        ]
        read_only_fields = ["id", "user_id", "provider", "provider_task_id",
                           "content_hash", "last_synced", "created_at", "updated_at"]

class TaskCreateSerializer(ModelSerializer):
    """For creating tasks via chat or direct API."""
    class Meta:
        model = Task
        fields = ["title", "description", "priority"]

class TaskMoveSerializer(Serializer):
    """For moving tasks between lists."""
    task_id = UUIDField()
    destination = CharField()  # 'prioritized', 'unprioritized', 'completed'
    position = IntegerField(required=False)

class TaskOrderSerializer(Serializer):
    """For reordering tasks within a list."""
    list_type = CharField()
    order = ListField(child=DictField())  # [{id, position}, ...]
```

### 2.2 Task ViewSet

```python
# aligned/viewsets/tasks.py

class TaskViewSet(ModelViewSet):
    queryset = Task
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = TaskPagination
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["title", "description"]
    ordering_fields = ["position", "priority", "due_date"]
    ordering = ["position"]

    def get_queryset(self):
        """Scope to current user. Optionally filter by list_type/status."""
        # Base: user's tasks only
        # Query params: ?list_type=prioritized&status=active
        ...

    @action(methods=["get"], detail=False, url_path="by-list")
    async def by_list(self, request, **kwargs):
        """GET /api/tasks/by-list — returns {prioritized, unprioritized, completed}."""
        ...

    @action(methods=["post"], detail=False, url_path="move")
    async def move_task(self, request, **kwargs):
        """POST /api/tasks/move — move task between lists."""
        ...

    @action(methods=["post"], detail=False, url_path="reorder")
    async def reorder(self, request, **kwargs):
        """POST /api/tasks/reorder — update positions within a list."""
        ...

    @action(methods=["post"], detail=False, url_path="sync")
    async def sync(self, request, **kwargs):
        """POST /api/tasks/sync — trigger sync from all providers."""
        ...

    @action(methods=["post"], detail=True, url_path="update-status")
    async def update_status(self, request, **kwargs):
        """POST /api/tasks/{pk}/update-status — update status + sync to provider."""
        ...
```

### 2.3 Port Task Providers

Port the provider pattern as-is. Key changes:

- **TaskProvider base class** — keep the ABC interface, make methods async
- **TodoistProvider** — port fully, async HTTP calls via `httpx`
- **GoogleTaskProvider** — port as-is (partial implementation)
- **OutlookTaskProvider** — port as-is (partial implementation)
- **TaskManager** — coordinator that instantiates providers, make async

The provider code is business logic, not REST layer. It stays largely the same, just needs:
1. `async def` on all methods
2. `AsyncSession` parameter instead of `db.session` global
3. `httpx.AsyncClient` instead of sync HTTP calls where applicable

### 2.4 Todoist Auth Routes

Port `todoist_routes.py` — OAuth callback for Todoist API key setup:

```python
# Non-viewset routes for OAuth callbacks
@router.get("/api/todoist/callback")
async def todoist_callback(request):
    """Handle Todoist OAuth callback, store API key in ExternalAccount."""
    ...
```

### 2.5 Token Refresh Background Task

Port `token_refresh.py` as a FastAPI startup event:

```python
# In app.py
@app.on_event("startup")
async def start_token_refresh():
    asyncio.create_task(token_refresh_loop())
```

This replaces the threading approach with native asyncio.

### 2.6 Task Sync Service

Port `sync_provider_tasks()` and `Task.create_or_update_from_provider_task()` as an async service:

```python
# aligned/services/task_sync.py

async def sync_provider_tasks(session, user_id, task_user_email, provider_name, provider_tasks):
    """Sync tasks from a provider to the database."""
    ...

async def sync_task_deletions(session, user_id, provider, current_ids):
    """Remove tasks no longer in provider."""
    ...
```

### 2.7 Vue Frontend — Task List

`frontend/src/views/TasksView.vue`:
- Three columns/sections: Prioritized, Unprioritized, Completed
- Drag-and-drop between lists (use `vuedraggable` or `@vueuse/integrations/useSortable`)
- Task cards showing title, priority badge, due date, project name
- Click to expand/edit task details
- Sync button triggers `POST /api/tasks/sync`
- Status toggle (complete/uncomplete)

`frontend/src/stores/tasks.ts` (Pinia):
- `prioritized`, `unprioritized`, `completed` arrays
- `fetchTasks()`, `moveTask()`, `reorderTasks()`, `syncTasks()`, `updateStatus()` actions

`frontend/src/api/tasks.ts`:
- API client functions wrapping axios calls to task endpoints

### 2.8 API Endpoints Summary

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/tasks` | List tasks (filterable, paginated) |
| POST | `/api/tasks` | Create task |
| GET | `/api/tasks/{pk}` | Get task details |
| PUT | `/api/tasks/{pk}` | Update task |
| PATCH | `/api/tasks/{pk}` | Partial update |
| DELETE | `/api/tasks/{pk}` | Delete task |
| GET | `/api/tasks/by-list` | Get tasks grouped by list type |
| POST | `/api/tasks/move` | Move task between lists |
| POST | `/api/tasks/reorder` | Reorder within a list |
| POST | `/api/tasks/sync` | Sync from providers |
| POST | `/api/tasks/{pk}/update-status` | Update status + provider sync |

### 2.9 Tests

**Unit tests:**
- Task serializer validation (priority range, status enum)
- TaskManager provider instantiation
- `sync_provider_tasks` logic with mock providers
- Task ordering logic (`move_task`, `update_task_order`)

**Integration tests:**
- Full CRUD via API (`GET /api/tasks`, `POST /api/tasks`, etc.)
- `by-list` endpoint returns correct grouping
- `move` and `reorder` update positions correctly
- `sync` endpoint calls providers and updates DB
- `update-status` syncs back to provider
- Auth: all endpoints return 401 without token
- Auth: tasks scoped to current user (can't see other users' tasks)

**E2E tests (Playwright):**
- Task list page loads with three sections
- Create a task, see it appear in unprioritized
- Drag task from unprioritized to prioritized
- Complete a task, see it move to completed
- Sync button triggers sync, tasks appear
- Task details expand on click

## Acceptance Criteria

- [ ] All task CRUD endpoints work with proper serialization
- [ ] Task list grouped by list_type via `by-list` endpoint
- [ ] Drag-and-drop reordering persists via API
- [ ] Provider sync creates/updates/deletes tasks in DB
- [ ] Status changes sync back to provider (Todoist at minimum)
- [ ] Token refresh runs as async background task
- [ ] Vue task page fully functional
- [ ] All tests pass
- [ ] OpenAPI docs show all task endpoints with schemas
