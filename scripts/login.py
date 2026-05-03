"""Playwright login helper for the Underway app.

Handles both flows:
  - Persistent profile + active Google session → redirects straight to target route
  - Google account chooser (prompt=select_account) → click the matching account tile
"""
from playwright.sync_api import Page


def login(page: Page, email: str, target_route: str = "/chat") -> None:
    """Click the Google sign-in button and complete OAuth, ending at target_route.

    Caller is responsible for navigating to a page that shows #g_id_signin
    (e.g. /login) before invoking. Page timeouts are taken from the page's
    default timeout — set it via page.set_default_timeout() upstream.
    """
    btn = page.locator("#g_id_signin")
    btn.wait_for(state="visible")
    btn.click()

    # After click, we either bounce through Google's account chooser or land
    # directly on the target route (depends on session state + prompt config).
    page.wait_for_url(lambda u: "accountchooser" in u or target_route in u)

    if "accountchooser" in page.url:
        page.get_by_text(email, exact=True).first.click()
        page.wait_for_url(f"**{target_route}**")
    else:
        pass

    page.wait_for_load_state("networkidle")
