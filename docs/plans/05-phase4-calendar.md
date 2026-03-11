# Phase 4: Calendar System

## Goal

Port calendar providers (Google Calendar, O365), OAuth flows, and event management. Build the Vue calendar management page.

## Source Files

| Original | New |
|----------|-----|
| `meetings/calendar_provider.py` | `underway/providers/calendar/base.py` |
| `meetings/calendar_provider_factory.py` | `underway/providers/calendar/factory.py` |
| `meetings/google_calendar_provider.py` | `underway/providers/calendar/google.py` |
| `meetings/o365_calendar_provider.py` | `underway/providers/calendar/o365.py` |
| `meetings/meetings_routes.py` | `underway/viewsets/calendar.py` + `underway/viewsets/oauth.py` |
| `templates/meetings.html` | `frontend/src/views/CalendarView.vue` |

## Steps

### 4.1 Port Calendar Providers

Port the provider pattern with async methods:

```python
# underway/providers/calendar/base.py

class CalendarProvider(ABC):
    @abstractmethod
    async def authenticate(self, email: str, user_id: UUID) -> bool: ...

    @abstractmethod
    async def get_events(self, email: str, user_id: UUID,
                         start: datetime, end: datetime) -> list[CalendarEvent]: ...

    @abstractmethod
    async def create_event(self, email: str, user_id: UUID,
                           event: CalendarEventCreate) -> CalendarEvent: ...

    @abstractmethod
    async def delete_event(self, email: str, user_id: UUID,
                           event_id: str) -> bool: ...
```

**GoogleCalendarProvider** — convert to async:
- Use `httpx.AsyncClient` for Google Calendar API calls
- Async token refresh using stored credentials from ExternalAccount
- Keep existing OAuth flow structure

**O365CalendarProvider** — convert to async:
- Use `httpx.AsyncClient` for Microsoft Graph API calls
- MSAL token acquisition stays sync (it's a local operation), wrap in `run_in_executor` if needed

### 4.2 Calendar Event Pydantic Models

Since calendar events come from external APIs (not our DB), use Pydantic models directly:

```python
# underway/providers/calendar/models.py

class CalendarEvent(BaseModel):
    id: str
    title: str
    start: datetime
    end: datetime
    location: str | None = None
    description: str | None = None
    provider: str

class CalendarEventCreate(BaseModel):
    title: str
    start: datetime
    end: datetime
    location: str | None = None
    description: str | None = None
```

### 4.3 OAuth Callback Routes

OAuth callbacks are redirects from external providers — they don't fit viewset patterns:

```python
# underway/viewsets/oauth.py

@router.get("/api/oauth/google/callback")
async def google_oauth_callback(request: Request):
    """Handle Google OAuth callback for calendar/tasks access."""
    # 1. Exchange auth code for tokens
    # 2. Store in ExternalAccount
    # 3. Redirect to frontend settings page
    ...

@router.get("/api/oauth/o365/callback")
async def o365_oauth_callback(request: Request):
    """Handle O365 OAuth callback."""
    ...

@router.post("/api/oauth/google/initiate")
async def initiate_google_oauth(request: Request):
    """Return the Google OAuth URL for the frontend to redirect to."""
    ...

@router.post("/api/oauth/o365/initiate")
async def initiate_o365_oauth(request: Request):
    """Return the O365 OAuth URL."""
    ...
```

### 4.4 Calendar ViewSet

```python
# underway/viewsets/calendar.py

class CalendarViewSet(ViewSet):
    """Non-model viewset for calendar operations (events are external)."""
    permission_classes = [IsAuthenticated]

    @action(methods=["get"], detail=False)
    async def events(self, request, **kwargs):
        """GET /api/calendar/events?start=...&end=... — list events."""
        ...

    @action(methods=["post"], detail=False)
    async def create_event(self, request, **kwargs):
        """POST /api/calendar/create-event — create calendar event."""
        ...

    @action(methods=["delete"], detail=False, url_path="delete-event")
    async def delete_event(self, request, **kwargs):
        """DELETE /api/calendar/delete-event — delete calendar event."""
        ...

    @action(methods=["post"], detail=False, url_path="set-primary")
    async def set_primary(self, request, **kwargs):
        """POST /api/calendar/set-primary — set primary calendar account."""
        ...
```

### 4.5 ExternalAccount Management Extensions

Add endpoints for account management (extends Phase 1 ExternalAccount viewset):

```python
@action(methods=["post"], detail=True, url_path="set-primary-calendar")
async def set_primary_calendar(self, request, **kwargs):
    ...

@action(methods=["post"], detail=True, url_path="set-primary-tasks")
async def set_primary_tasks(self, request, **kwargs):
    ...

@action(methods=["delete"], detail=True)
async def destroy(self, request, **kwargs):
    """Delete account — if also used for other purpose, just clear the flag."""
    ...
```

### 4.6 Vue Frontend — Calendar Management

`frontend/src/views/CalendarView.vue`:
- List connected calendar accounts
- "Connect Google Calendar" / "Connect O365" buttons → initiate OAuth flow
- Primary calendar toggle
- Calendar event list for today/this week
- Remove account button

`frontend/src/stores/calendar.ts` (Pinia):
- `accounts`, `events` state
- `connectGoogle()`, `connectO365()`, `fetchEvents()`, `setPrimary()`

### 4.7 API Endpoints Summary

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/calendar/events` | List events for date range |
| POST | `/api/calendar/create-event` | Create calendar event |
| DELETE | `/api/calendar/delete-event` | Delete calendar event |
| POST | `/api/calendar/set-primary` | Set primary calendar |
| POST | `/api/oauth/google/initiate` | Start Google OAuth |
| GET | `/api/oauth/google/callback` | Google OAuth callback |
| POST | `/api/oauth/o365/initiate` | Start O365 OAuth |
| GET | `/api/oauth/o365/callback` | O365 OAuth callback |

### 4.8 Tests

**Unit tests:**
- CalendarProvider mock implementations
- OAuth URL generation
- Token storage/refresh logic
- CalendarEvent model validation

**Integration tests:**
- OAuth initiate returns valid redirect URL
- OAuth callback stores credentials in ExternalAccount
- Events endpoint returns data from mock provider
- Set primary calendar updates ExternalAccount
- Account deletion handles dual-use (calendar + tasks)

**E2E tests (Playwright):**
- Calendar page loads, shows connected accounts
- Connect button initiates OAuth flow (mock the redirect)
- Events display for connected calendar
- Primary toggle works
- Remove account works

## Acceptance Criteria

- [ ] Google Calendar provider works async (get events, create event, delete)
- [ ] O365 provider works async
- [ ] OAuth flows work end-to-end for both providers
- [ ] Primary calendar account management works
- [ ] Account deletion handles dual-use correctly
- [ ] Token refresh works for calendar tokens
- [ ] Vue calendar page functional
- [ ] All tests pass
