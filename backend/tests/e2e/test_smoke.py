"""E2E smoke tests — verify frontend, backend, and auth are wired together."""

import pytest
from playwright.sync_api import Page


@pytest.mark.e2e
def test_frontend_loads(base_url: str, page: Page) -> None:
    """Vue app loads and shows the login page for unauthenticated users."""
    page.goto(base_url)
    page.wait_for_load_state("domcontentloaded")
    assert page.title() != ""


@pytest.mark.e2e
def test_api_health(base_url: str, page: Page) -> None:
    """Backend health endpoint is reachable."""
    response = page.request.get(f"{base_url}/api/health")
    assert response.status == 200
    assert response.json()["status"] == "ok"


@pytest.mark.e2e
def test_authenticated_settings_page(base_url: str, authenticated_page: Page) -> None:
    """Authenticated user can reach the settings page."""
    authenticated_page.goto(f"{base_url}/settings")
    heading = authenticated_page.locator("h1")
    heading.wait_for(state="visible")
    assert heading.text_content() == "Settings"
