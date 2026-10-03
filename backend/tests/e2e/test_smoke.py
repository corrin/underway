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
def test_tasks_api_requires_auth_returns_401_not_500(base_url: str, page: Page) -> None:
    """Regression: an unauthenticated /api/tasks request must return 401, never 500.

    Every viewset used to run as AllowAny — fastrest's base APIView sets
    permission_classes=[AllowAny] as a class attribute, which shadowed the configured
    IsAuthenticated default. Anonymous requests therefore reached the handler and crashed
    on request.user.id (AttributeError -> 500). It must now be a clean 401.
    """
    response = page.request.get(f"{base_url}/api/tasks")
    assert response.status == 401, f"expected 401 for anonymous /api/tasks, got {response.status}"


@pytest.mark.e2e
def test_protected_route_redirects_unauthenticated_to_login(base_url: str, page: Page) -> None:
    """An unauthenticated visit to a protected route redirects to /login (no broken page)."""
    page.goto(f"{base_url}/tasks")
    page.wait_for_url("**/login**")
    assert "/login" in page.url


@pytest.mark.e2e
def test_authenticated_settings_page(base_url: str, authenticated_page: Page) -> None:
    """Authenticated user can reach the settings page."""
    authenticated_page.goto(f"{base_url}/settings")
    heading = authenticated_page.locator("h1")
    heading.wait_for(state="visible")
    assert heading.text_content() == "Settings"
