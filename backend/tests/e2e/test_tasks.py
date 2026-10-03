"""Real e2e test: Google Tasks → Underway combined-list sync.

Exercises the actual linkages end-to-end against a real Google Tasks account and the
running app (via ngrok): a task created in Google must appear in Underway after a sync,
an upstream edit must be reflected, and an upstream delete must be reconciled away. It
fails loudly if any of those don't happen.

Drives BOTH the UI (clicking Sync on /tasks) and the API (POST /api/tasks/sync,
GET /api/tasks). See conftest.py for prerequisites; run via scripts/run-e2e.sh.
"""

from typing import Any

import pytest
from playwright.sync_api import APIResponse, Page

from tests.e2e.conftest import GoogleTasksSandbox, unique_sentinel


def _jwt(page: Page) -> str:
    token = page.evaluate("() => localStorage.getItem('token')")
    assert token, "expected a JWT in localStorage after authentication"
    return str(token)


def _api_get_tasks(page: Page, base_url: str, headers: dict[str, str]) -> list[dict[str, Any]]:
    resp: APIResponse = page.request.get(f"{base_url}/api/tasks", headers=headers)
    assert resp.ok, f"GET /api/tasks failed: {resp.status}"
    tasks: list[dict[str, Any]] = resp.json()
    return tasks


def _api_sync(page: Page, base_url: str, headers: dict[str, str]) -> None:
    resp: APIResponse = page.request.post(f"{base_url}/api/tasks/sync", headers=headers)
    assert resp.ok, f"POST /api/tasks/sync failed: {resp.status}"


@pytest.mark.e2e
def test_google_task_syncs_into_list_and_reconciles(
    base_url: str,
    google_tasks: GoogleTasksSandbox,
    authenticated_page: Page,
) -> None:
    page = authenticated_page
    headers = {"Authorization": f"Bearer {_jwt(page)}"}

    sentinel = unique_sentinel()
    task_id = google_tasks.create(sentinel)

    # --- UI: clicking Sync pulls the new Google task onto the board ---
    page.goto(f"{base_url}/tasks")
    page.locator("h1", has_text="Tasks").wait_for(state="visible")
    page.get_by_role("button", name="Sync", exact=True).click()
    page.locator(".task-card", has_text=sentinel).first.wait_for(state="visible")
    assert page.locator(".error-banner").count() == 0

    # --- API: it's in the combined list, tagged as a Google Tasks item ---
    matches = [t for t in _api_get_tasks(page, base_url, headers) if t["title"] == sentinel]
    assert len(matches) == 1, f"sentinel {sentinel!r} did not sync into /api/tasks"
    assert matches[0]["provider"] == "google_tasks"

    # --- upstream edit is reflected after sync (content-hash update path) ---
    updated = f"{sentinel}-UPDATED"
    google_tasks.update_title(task_id, updated)
    _api_sync(page, base_url, headers)
    titles_after_update = {t["title"] for t in _api_get_tasks(page, base_url, headers)}
    assert updated in titles_after_update, "upstream title change was not synced"
    assert sentinel not in titles_after_update, "stale pre-edit title lingered after sync"

    # --- upstream delete is reconciled away (sync_task_deletions) ---
    google_tasks.delete(task_id)
    _api_sync(page, base_url, headers)
    titles_after_delete = {t["title"] for t in _api_get_tasks(page, base_url, headers)}
    assert updated not in titles_after_delete, "task remained after upstream deletion"
