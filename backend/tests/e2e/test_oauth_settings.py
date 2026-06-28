"""E2E tests for OAuth flow UX on the Settings page.

Reproduces two bugs:
1. Denying consent on the provider's screen (Microsoft sends ?error=access_denied)
   used to surface raw JSON: {"detail":"Missing code or state parameter."}.
   It should redirect to /settings with a friendly "cancelled" banner.

2. The "connected successfully" banner persisted across reloads/clicks because
   the ?oauth=success query param was never stripped from the URL. Refreshing
   would still show the stale banner.
"""

import pytest
from playwright.sync_api import Page


@pytest.mark.e2e
def test_o365_deny_redirects_to_cancelled_settings(base_url: str, page: Page) -> None:
    """Hitting the O365 callback with ?error=access_denied (deny path) should
    redirect to /settings with the cancelled status, not surface raw JSON."""
    response = page.request.get(
        f"{base_url}/api/oauth/o365/callback?error=access_denied&error_description=User+denied",
        max_redirects=0,
    )
    assert response.status == 307
    assert response.headers["location"] == "/settings?oauth=cancelled&provider=o365"


@pytest.mark.e2e
def test_google_deny_redirects_to_cancelled_settings(base_url: str, page: Page) -> None:
    """Same deny-path UX for the Google callback."""
    response = page.request.get(
        f"{base_url}/api/oauth/google/callback?error=access_denied",
        max_redirects=0,
    )
    assert response.status == 307
    assert response.headers["location"] == "/settings?oauth=cancelled&provider=google"


@pytest.mark.e2e
def test_success_banner_does_not_persist_across_reload(base_url: str, authenticated_page: Page) -> None:
    """Visiting /settings?oauth=success should show the banner once, then strip
    the query param so a reload doesn't re-show it."""
    authenticated_page.goto(f"{base_url}/settings?oauth=success&provider=o365")
    banner = authenticated_page.locator(".banner--success")
    banner.wait_for(state="visible")

    # URL should have been cleaned up by the page (query stripped)
    authenticated_page.wait_for_function("() => !window.location.search.includes('oauth=')")

    # Reload should NOT re-show the success banner
    authenticated_page.reload()
    authenticated_page.wait_for_load_state("domcontentloaded")
    authenticated_page.wait_for_selector("h1", state="visible")
    assert authenticated_page.locator(".banner--success").count() == 0
