# Contributing

## Setup

```bash
./scripts/setup-db.sh                            # creates underway user + _dev/_test DBs; DB_PASSWORD=... to override
cp backend/.env.example backend/.env             # set DATABASE_URL only if you overrode the default password
cp ngrok.yml.example ngrok.yml                   # add authtoken; leave domain alone

( cd backend  && poetry install && poetry run alembic upgrade head )
( cd frontend && npm install )
```

Run via VS Code's **Full Stack** compound. Backend logs land in the Debug Console.

## Project specifics

- **ngrok domain is fixed at `underway-lakeland.ngrok.io`** — Google's OAuth client only has that one redirect URI registered. `BASE_URL`, all `*_REDIRECT_URI` values, and `ngrok.yml`'s `domain:` must match. Browser too — never `localhost`.
- **`Settings` runs `extra='forbid'`.** Add new keys to the class; don't loosen the model.
- **Every `if` has an explicit `else`.** Even `else: pass  # ...`. Pre-existing offenders are tech debt — don't sweep.
- **No `# type: ignore`, `# noqa`, `per-file-ignores`, or disabled ruff rules.** Use `backend/stubs/*.pyi` or `typing.cast`.
- **`fastrest`** drives viewsets — see [docs/fastrest-reference.md](docs/fastrest-reference.md).
- **`underway_test` is dropped/rebuilt per test.** Migrations apply to `_dev` only.

## Common errors

| Symptom | Fix |
|---|---|
| `redirect_uri_mismatch` | `BASE_URL` / redirect URIs / `ngrok.yml` domain don't all match the registered host |
| `OperationalError (1045) Access denied 'underway'@'localhost'` | Wrong DB password — re-run `CREATE USER`, or set `DATABASE_URL` |
| `ValidationError: extra_forbidden` on startup | `.env` has a key not on `Settings` — declare, move, or delete |
| 401 on first load | Sign in |
