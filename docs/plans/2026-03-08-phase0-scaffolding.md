# Phase 0: Project Scaffolding — COMPLETED 2026-03-08

**Goal:** Set up the aligned repo with backend (FastAPI/FastREST), frontend (Vue/TypeScript), strict type checking, testing, and CI.

**Status:** All tasks complete. All quality gates passing.

## What was built

### Backend (`backend/`)
- **Framework:** FastAPI with app factory pattern (`aligned/app.py`)
- **Config:** pydantic-settings with `.env` support (`aligned/config.py`)
- **Database:** Async SQLAlchemy + Alembic migrations (`aligned/models/`, `migrations/`)
- **Dependencies:** Poetry with lockfile (`pyproject.toml`, `poetry.lock`)
- **Quality:** mypy strict, ruff, pre-commit hooks
- **Testing:** pytest with async fixtures, Playwright e2e (excluded from default run via `-m 'not e2e'`)
- **Python:** ^3.12

### Frontend (`frontend/`)
- **Framework:** Vue 3 + TypeScript strict + Pinia + Vue Router
- **Build:** Vite with API proxy to backend (`:8000`)
- **Quality:** ESLint (essential + typescript-eslint), vue-tsc
- **Allowed hosts:** `.ngrok.io`, `.ngrok-free.app`

### CI/CD
- **GitHub Actions:** `.github/workflows/ci.yml` — backend (mypy, ruff, pytest) + frontend (eslint, vue-tsc, build)

### Dev Environment
- **VS Code:** Full Stack compound launch (backend debugger + frontend + ngrok) in `.vscode/launch.json`
- **ngrok:** Per-project config (`ngrok.yml`), global authtoken in `~/.ngrok2/ngrok.yml`
- **Pre-commit:** ruff check, ruff format, mypy strict on `backend/` files

## Key decisions & deviations from original plan
- Switched from pip/setuptools to **Poetry** for dependency management
- Pre-commit config placed at **repo root** (not `backend/`) — that's where git looks
- Added **ESLint** (not in original plan) with `flat/essential` + typescript-eslint
- Added **`BASE_URL`** setting for dev/UAT domain config
- E2e tests use **port 8001/5174** to avoid conflicts with dev servers
- E2e tests **excluded from default pytest run** (sync Playwright conflicts with async fixtures)
- Added `migrations/**` to ruff ANN ignores

## Commands
```bash
# Setup
cd backend && poetry install

# Dev server (or use VS Code "Full Stack" launch)
poetry run uvicorn aligned.app:create_app --factory --port 8000 --reload

# Quality gates
poetry run mypy aligned --strict
poetry run ruff check aligned
poetry run pytest -v
poetry run pytest -m e2e  # separate, needs servers

# Frontend
cd frontend && npm ci
npm run lint
npm run build
```
