# Phase 1: Foundation — COMPLETED 2026-03-08

**Goal:** Port all SQLAlchemy models to async, implement JWT authentication with Google Sign-In, and build the settings/user management API + Vue pages.

**Status:** All tasks complete. All quality gates passing. PR #1 merged.

## What was built

### Backend
- **Models:** User, ExternalAccount, Task, Conversation, ChatMessage — all async SQLAlchemy 2.0 with `mapped_column`, `AsyncSession`
- **Auth:** JWT authentication (`aligned/auth/jwt.py`), Google ID token verification (`aligned/auth/google.py`)
- **Routes:** Google login, logout, /me (`aligned/routes/auth.py`), settings CRUD (`aligned/routes/settings.py`)
- **ViewSets:** ExternalAccount read-only viewset (`aligned/viewsets/external_accounts.py`)
- **Serializers:** User settings, ExternalAccount — all with `ClassVar` annotations
- **Dependencies:** `Annotated` type aliases for DI (`BearerCredentials`, `DbSession`, `CurrentSettings`)
- **Test auth bypass:** `/api/auth/test-login` endpoint (only registered when `TESTING=true`) for Playwright E2E

### Frontend
- **Login:** Google Sign-In → JWT flow (`LoginView.vue`)
- **Settings:** User preferences form + external accounts list (`SettingsView.vue`)
- **Auth store:** Pinia store with token management, axios interceptor (`stores/auth.ts`)
- **Router guard:** Redirects unauthenticated users to `/login`

### Tests
- Unit: JWT creation/verification, Google token verification (mocked)
- Integration: Auth endpoints, settings CRUD, external accounts
- E2E: Login page, settings page, authenticated smoke test

## Key decisions
- JWT stored in localStorage (not httpOnly cookie) — simpler for SPA
- `Annotated` types throughout to avoid ruff B008 (no `Depends()` in defaults)
- `ClassVar` on serializer Meta fields for RUF012
- Test-login bypass for Playwright (conditionally registered, absent in production)
