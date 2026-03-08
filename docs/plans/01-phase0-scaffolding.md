# Phase 0: Project Scaffolding

## Goal

Set up the aligned repo with strict tooling guardrails so that every line of code written from Phase 1 onward is type-checked, linted, and tested. This phase is deliberately careful — it's cheaper to get the foundations right now than to retrofit them later.

## Principles

- **mypy strict from line one.** Every function has type annotations. No `Any` escapes. If a third-party library lacks stubs, add a minimal stub or typed wrapper — don't `# type: ignore` it.
- **Ruff enforces style.** No debates about formatting. CI fails on lint violations.
- **Tests run before every commit.** Pre-commit hooks run mypy + ruff + pytest. If it doesn't pass, it doesn't land.
- **OpenAPI is the source of truth.** FastREST generates schemas from serializers. The Vue frontend can generate its API client from the OpenAPI spec. No hand-maintained API docs.

## Steps

### 0.1 Backend Setup

Create `backend/pyproject.toml` with:

```toml
[project]
name = "aligned"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.100",
    "fastrest[sqlalchemy]",
    "uvicorn[standard]",
    "sqlalchemy[asyncio]>=2.0",
    "aiomysql",
    "pydantic>=2.0",
    "pydantic-settings",
    "python-dotenv",
    "pyjwt[crypto]",
    "httpx",
    "litellm",
    "todoist-api-python",
    "O365",
    "msal",
    "google-api-python-client",
    "google-auth-oauthlib",
    "alembic",
]

[project.optional-dependencies]
dev = [
    "pytest",
    "pytest-asyncio",
    "pytest-playwright",
    "playwright",
    "mypy",
    "ruff",
    "black",
]
```

Create minimal `backend/aligned/__init__.py` and `backend/aligned/app.py`:

```python
from fastapi import FastAPI

def create_app() -> FastAPI:
    app = FastAPI(title="Aligned")
    return app
```

### 0.2 Database Setup

Create `backend/aligned/models/__init__.py` with async SQLAlchemy engine setup:

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass
```

Initialize Alembic with async support:

```bash
cd backend
alembic init -t async migrations
```

Configure `alembic.ini` and `env.py` to use `aligned.models.Base.metadata`.

### 0.3 Frontend Setup

```bash
cd frontend
npm create vue@latest . -- --typescript --router --pinia
npm install axios
npm install -D @playwright/test
```

Configure Vite to proxy `/api` to `http://localhost:8000` in development.

### 0.4 Configuration

Create `backend/.env.example`:

```env
DATABASE_URL=mysql+aiomysql://user:pass@localhost:3306/aligned
JWT_SECRET_KEY=change-me
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=...
O365_CLIENT_ID=...
O365_CLIENT_SECRET=...
O365_REDIRECT_URI=...
```

Create `backend/aligned/config.py` using pydantic-settings:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    jwt_secret_key: str
    google_client_id: str = ""
    google_client_secret: str = ""
    # ... etc

    class Config:
        env_file = ".env"
```

### 0.5 Testing Infrastructure

Create test directories and fixtures:

```
backend/tests/
├── conftest.py          # Async DB fixtures, test app, APIClient
├── unit/
│   └── __init__.py
├── integration/
│   └── __init__.py
└── e2e/
    ├── conftest.py      # Playwright fixtures
    └── __init__.py
```

`backend/tests/conftest.py` — set up:
- In-memory SQLite async engine for unit/integration tests
- FastREST `APIClient` wired to test app
- User factory fixture

`backend/tests/e2e/conftest.py` — set up:
- Playwright browser fixture
- Dev server startup (backend + frontend)
- Test database seeding

### 0.6 Code Quality — The Hard Gate

This is the most important step. Everything after this must pass these checks.

**mypy config** in `backend/pyproject.toml`:

```toml
[tool.mypy]
strict = true
plugins = ["pydantic.mypy"]
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_any_generics = true
check_untyped_defs = true
no_implicit_reexport = true

# Per-module overrides only for third-party libs that truly lack stubs.
# Each override must have a comment explaining why it's needed.
# [[tool.mypy.overrides]]
# module = "some_untyped_lib.*"
# ignore_missing_imports = true
```

**Ruff config:**

```toml
[tool.ruff]
line-length = 120
target-version = "py312"

[tool.ruff.lint]
select = [
    "E", "W",   # pycodestyle
    "F",         # pyflakes
    "I",         # isort
    "UP",        # pyupgrade
    "B",         # flake8-bugbear
    "SIM",       # flake8-simplify
    "TCH",       # flake8-type-checking
    "ANN",       # flake8-annotations (enforce type hints)
    "RUF",       # ruff-specific rules
]
```

**pytest config:**

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
strict_markers = true
```

**Pre-commit hooks** — create `backend/.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: ruff-check
        name: ruff check
        entry: ruff check --fix
        language: system
        types: [python]
      - id: ruff-format
        name: ruff format
        entry: ruff format
        language: system
        types: [python]
      - id: mypy
        name: mypy
        entry: mypy aligned
        language: system
        types: [python]
        pass_filenames: false
```

Install with `pre-commit install` so these run on every `git commit`.

**Frontend type checking** — in `frontend/tsconfig.json`:

```json
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true
  }
}
```

Vue uses TypeScript strict mode. ESLint + Prettier configured by `create-vue`.

### 0.7 GitHub Actions CI

Create `.github/workflows/ci.yml` at the repo root:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  backend:
    runs-on: ubuntu-latest
    services:
      mysql:
        image: mysql:8.0
        env:
          MYSQL_ROOT_PASSWORD: test
          MYSQL_DATABASE: aligned_test
        ports:
          - 3306:3306
        options: >-
          --health-cmd="mysqladmin ping"
          --health-interval=10s
          --health-timeout=5s
          --health-retries=3
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install dependencies
        working-directory: backend
        run: pip install -e ".[dev]"
      - name: mypy
        working-directory: backend
        run: mypy aligned --strict
      - name: ruff check
        working-directory: backend
        run: ruff check aligned
      - name: ruff format
        working-directory: backend
        run: ruff format --check aligned
      - name: pytest
        working-directory: backend
        env:
          DATABASE_URL: mysql+aiomysql://root:test@localhost:3306/aligned_test
          JWT_SECRET_KEY: test-secret
        run: pytest

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
      - name: Install dependencies
        working-directory: frontend
        run: npm ci
      - name: Type check
        working-directory: frontend
        run: npx vue-tsc --noEmit
      - name: Lint
        working-directory: frontend
        run: npm run lint

  e2e:
    runs-on: ubuntu-latest
    needs: [backend, frontend]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
      - name: Install backend
        working-directory: backend
        run: pip install -e ".[dev]"
      - name: Install frontend
        working-directory: frontend
        run: npm ci
      - name: Install Playwright browsers
        working-directory: backend
        run: playwright install --with-deps chromium
      - name: Run e2e tests
        working-directory: backend
        env:
          DATABASE_URL: sqlite+aiosqlite:///test.db
          JWT_SECRET_KEY: test-secret
        run: pytest tests/e2e/
```

CI runs on every push to main and every PR. Backend quality gates (mypy, ruff, pytest) and frontend type checking must all pass. PRs cannot merge with failures.

**Configure branch protection** on GitHub:
- Require status checks to pass before merging (backend, frontend, e2e jobs)
- Require PR reviews

### 0.8 Verify the Gate Works

Before the smoke test, write a deliberately broken file and confirm:
1. `mypy aligned` catches an untyped function — fails
2. `ruff check aligned` catches a style violation — fails
3. `git commit` is blocked by pre-commit hooks

Delete the broken file. Now we know the guardrails work.

### 0.8 Smoke Test

Write a minimal test that:
1. Creates the FastAPI app
2. Hits `GET /` and gets a response
3. Playwright opens the Vue app and sees the page title

This validates the full stack is wired together before any features are ported.

## Acceptance Criteria

**Build & run:**
- [ ] `cd backend && pip install -e ".[dev]"` works
- [ ] `cd frontend && npm install && npm run dev` works
- [ ] `cd backend && alembic upgrade head` runs (empty migration)
- [ ] Vite proxies `/api/*` to FastAPI backend

**Quality gates — these must pass on every commit going forward:**
- [ ] `mypy aligned --strict` passes with zero errors
- [ ] `ruff check aligned` passes with zero violations
- [ ] `ruff format --check aligned` passes
- [ ] `pre-commit run --all-files` passes
- [ ] `cd frontend && npx vue-tsc --noEmit` passes (TypeScript strict)

**Tests:**
- [ ] `cd backend && pytest` passes (smoke test)
- [ ] Playwright smoke test opens Vue app, sees page title
- [ ] A deliberately untyped function is caught by mypy (verify, then delete)

**CI:**
- [ ] GitHub Actions CI passes on push to main
- [ ] CI runs mypy, ruff, pytest (backend) and vue-tsc, lint (frontend)
- [ ] Branch protection requires CI to pass before merging

**Ongoing rule:** No phase is complete unless all quality gates still pass. If a third-party library forces a `# type: ignore`, it must be documented with a comment explaining why and tracked as tech debt to resolve. Usually we write our own monkeypatch.
