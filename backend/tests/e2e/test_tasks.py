"""E2E tests for the tasks page, including provider sync.

Prerequisites (see tests/e2e/conftest.py): full stack running (backend on :9000,
frontend, ngrok), BASE_URL + PLAYWRIGHT_CHROME_PROFILE set, and at least one task
provider (e.g. Todoist) connected for the signed-in user with active tasks.
"""

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
def test_tasks_page_loads(base_url: str, authenticated_page: Page) -> None:
    """Tasks page loads with its heading and a Sync button."""
    authenticated_page.goto(f"{base_url}/tasks")
    heading = authenticated_page.locator("h1")
    heading.wait_for(state="visible")
    assert heading.inner_text() == "Tasks"

    sync_btn = authenticated_page.get_by_role("button", name="Sync", exact=True)
    sync_btn.wait_for(state="visible")


@pytest.mark.e2e
def test_sync_imports_provider_tasks(base_url: str, authenticated_page: Page) -> None:
    """Clicking Sync pulls tasks from the connected provider(s) into the board.

    Reproduces the gap that POST /api/tasks/sync used to be a stub: after wiring it to
    sync_all_task_accounts, a real sync must complete without error and surface tasks.
    """
    page = authenticated_page
    page.goto(f"{base_url}/tasks")
    page.locator("h1", has_text="Tasks").wait_for(state="visible")

    sync_btn = page.get_by_role("button", name="Sync", exact=True)
    sync_btn.wait_for(state="visible")
    sync_btn.click()

    # The button flips to "Syncing..." while in flight and returns to "Sync" when the
    # round-trip to POST /api/tasks/sync (and the follow-up refetch) completes.
    expect(sync_btn).to_be_enabled()

    # Sync must not have surfaced an error.
    assert page.locator(".error-banner").count() == 0

    # Tasks from the connected provider are now on the board.
    page.locator(".task-card").first.wait_for(state="visible")
    assert page.locator(".task-card").count() > 0
