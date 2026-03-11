# Migration Overview: virtual_assistant -> underway (FastREST)

## Why We're Doing This

The virtual_assistant codebase works, but accumulated tech debt: no type checking, no OpenAPI contract, Flask's sync model fighting against async providers, `db.session` globals scattered through business logic, mixed HTML/JSON endpoints, and inconsistent patterns across modules. The kind of ugliness you only see clearly after building the first version.

This rewrite is about setting the architecture right from day one:

- **Strict mypy** from the first file — no `# type: ignore` creep
- **OpenAPI as the contract** — FastREST auto-generates typed schemas from serializers, Vue consumes them
- **Async throughout** — no more `asyncio.new_event_loop()` hacks in sync Flask handlers
- **Clear boundaries** — models, serializers, viewsets, providers each have one job
- **Testable by design** — dependency injection over globals, async session parameters over `db.session`

The goal is feature parity. We're not adding features. We're rebuilding the same thing properly so it can grow without fighting itself.

## Key Decisions

| Decision | Choice |
|----------|--------|
| Framework | FastREST (FastAPI + SQLAlchemy async + Pydantic) |
| Frontend | Vue SPA (same repo, `frontend/` directory) |
| Auth | JWT tokens, Google Sign-In on frontend |
| Database | Fresh MySQL DB, new Alembic history |
| Testing | Playwright e2e + pytest unit/integration from day one |
| Name | `underway` throughout (no more `virtual_assistant`) |
| Approach | Port-and-adapt, phase by phase |

## Repo Structure

```
underway/
├── backend/
│   ├── underway/                # Python package
│   │   ├── models/             # SQLAlchemy async models
│   │   ├── serializers/        # FastREST serializers
│   │   ├── viewsets/           # FastREST viewsets
│   │   ├── providers/          # Task/calendar/AI providers
│   │   ├── auth/               # JWT auth, Google Sign-In verification
│   │   ├── chat/               # Chat + SSE streaming + tool calling
│   │   ├── schedule/           # Schedule generation
│   │   ├── config.py           # Settings (env vars)
│   │   └── app.py              # FastAPI app factory
│   ├── migrations/             # Alembic (fresh)
│   ├── tests/
│   │   ├── unit/               # Serializers, models, providers
│   │   ├── integration/        # API endpoints (FastREST APIClient)
│   │   └── e2e/                # Playwright browser tests
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── views/              # Vue pages
│   │   ├── components/         # Reusable components
│   │   ├── stores/             # Pinia stores
│   │   ├── api/                # API client (generated from OpenAPI)
│   │   └── router/             # Vue Router
│   ├── package.json
│   └── vite.config.ts
├── docs/
│   ├── plans/                  # These migration plans
│   └── fastrest-reference.md   # FastREST API reference
└── README.md
```

## Migration Phases

| Phase | Scope | Plan Doc |
|-------|-------|----------|
| 0 | Project scaffolding, tooling, CI | [01-phase0-scaffolding.md](01-phase0-scaffolding.md) |
| 1 | Models, JWT auth, Google Sign-In, settings | [02-phase1-foundation.md](02-phase1-foundation.md) |
| 2 | Task CRUD, provider sync, task management UI | [03-phase2-tasks.md](03-phase2-tasks.md) |
| 3 | Chat, SSE streaming, LLM tool calling | [04-phase3-chat.md](04-phase3-chat.md) |
| 4 | Calendar providers, OAuth flows, events | [05-phase4-calendar.md](05-phase4-calendar.md) |
| 5 | AI schedule generation | [06-phase5-schedule.md](06-phase5-schedule.md) |

Each phase delivers: API endpoints + Vue UI + tests (unit, integration, e2e).

## Quality Gates (Every Phase)

These must pass before any phase is considered complete. They are set up in Phase 0 and enforced by pre-commit hooks from that point forward.

- `mypy underway --strict` — zero errors, no `# type: ignore` without documented justification
- `ruff check underway` + `ruff format --check underway` — zero violations
- `pytest` — all tests pass (unit + integration + e2e)
- `npx vue-tsc --noEmit` — frontend TypeScript strict, zero errors
- OpenAPI spec at `/docs` reflects all endpoints with typed request/response schemas

The original virtual_assistant has no type checking, inconsistent validation, and `db.session` globals leaking through every layer. The whole point of this rewrite is that we don't repeat those patterns. If something is hard to type correctly, that's a signal to redesign the interface — not to add an escape hatch.

## Source Reference

The original codebase lives at `/home/corrin/src/virtual_assistant/`. Key mappings:

| Original | Underway |
|----------|---------|
| `virtual_assistant/database/user.py` | `underway/models/user.py` |
| `virtual_assistant/database/task.py` | `underway/models/task.py` |
| `virtual_assistant/database/external_account.py` | `underway/models/external_account.py` |
| `virtual_assistant/chat/models.py` | `underway/models/conversation.py` |
| `virtual_assistant/flask_app.py` | `underway/app.py` |
| `virtual_assistant/auth/user_auth.py` | `underway/auth/jwt.py` |
| `virtual_assistant/chat/chat_routes.py` | `underway/viewsets/chat.py` |
| `virtual_assistant/chat/tools.py` | `underway/chat/tools.py` |
| `virtual_assistant/tasks/task_routes.py` | `underway/viewsets/tasks.py` |
| `virtual_assistant/tasks/task_manager.py` | `underway/providers/task_manager.py` |
| `virtual_assistant/tasks/todoist_provider.py` | `underway/providers/todoist.py` |
| `virtual_assistant/meetings/` | `underway/providers/calendar/` |
| `virtual_assistant/schedule/` | `underway/schedule/` |
| `virtual_assistant/utils/settings.py` | `underway/config.py` |
| `virtual_assistant/templates/` | `frontend/src/views/` |
