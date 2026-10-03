#!/usr/bin/env bash
# Run the Playwright e2e suite.
#
# Prerequisites:
#   - Full stack running: backend on :9000, frontend, ngrok (BASE_URL).
#   - BASE_URL + PLAYWRIGHT_CHROME_PROFILE set in .env / .env.test.
#   - Your real Chrome CLOSED (the persistent profile can't be shared).
#   - For the Google Tasks sync test: a Google account connected for tasks
#     (Settings → re-auth Google, then "Use for tasks").
#
# pytest-asyncio's auto mode and pytest-playwright each inject a running event loop
# that breaks sync Playwright, so we disable both plugins here.
set -euo pipefail
cd "$(dirname "$0")/.."
exec poetry run pytest tests/e2e -m e2e -p no:asyncio -p no:playwright "$@"
