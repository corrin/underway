"""E2E smoke tests — verify frontend, backend, and auth are wired together."""

import pytest
from playwright.sync_api import Page


@pytest.mark.e2e
def test_frontend_loads(frontend_server: str, page: Page) -> None:
    """Vue app loads and shows the login page for unauthenticated users."""
    page.goto(frontend_server)
    page.wait_for_load_state("networkidle")
    assert page.title() != ""


@pytest.mark.e2e
def test_api_health(backend_server: str, page: Page) -> None:
    """Backend health endpoint is reachable."""
    response = page.request.get(f"{backend_server}/api/health")
    assert response.status == 200
    assert response.json()["status"] == "ok"


@pytest.mark.e2e
def test_authenticated_settings_page(frontend_server: str, authenticated_page: Page) -> None:
    """Authenticated user can reach the settings page."""
    authenticated_page.goto(f"{frontend_server}/settings")
    authenticated_page.wait_for_load_state("networkidle")
    assert authenticated_page.locator("h1").text_content() == "Settings"
