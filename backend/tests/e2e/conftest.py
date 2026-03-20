"""Playwright e2e test fixtures — uses real Chrome profile with Google auth.

Prerequisites: Full Stack must be running (backend, frontend, ngrok).

All fixtures use sync Playwright (sync_playwright).
"""

import os
from collections.abc import Generator
from pathlib import Path

import pytest
from dotenv import find_dotenv, load_dotenv
from playwright.sync_api import Page, sync_playwright

load_dotenv(find_dotenv())

# Global Playwright timeout — no individual timeout should exceed this.
E2E_TIMEOUT_MS = 10000

# Chrome profile with saved Google session.
# To set up: google-chrome --user-data-dir=<path>
# Then log into Google and close the browser.
# Add PLAYWRIGHT_CHROME_PROFILE=<path> to backend/.env
CHROME_PROFILE_DIR = os.environ.get("PLAYWRIGHT_CHROME_PROFILE", "")
BASE_URL = os.environ.get("BASE_URL", "")


@pytest.fixture(scope="session")
def base_url() -> str:
    """App base URL (ngrok)."""
    if not BASE_URL:
        pytest.skip("BASE_URL is not set. Add it to backend/.env")
    return BASE_URL


@pytest.fixture
def page() -> Generator[Page]:
    """Browser page for non-authenticated tests."""
    pw = sync_playwright().start()
    browser = pw.chromium.launch()
    p = browser.new_page()
    p.set_default_timeout(E2E_TIMEOUT_MS)
    p.set_default_navigation_timeout(E2E_TIMEOUT_MS)

    yield p

    browser.close()
    pw.stop()


@pytest.fixture
def authenticated_page(
    base_url: str,
) -> Generator[Page]:
    """Page with real Google auth via persistent Chrome profile."""
    if not CHROME_PROFILE_DIR:
        pytest.skip("PLAYWRIGHT_CHROME_PROFILE is not set. Add it to backend/.env")
    # Remove stale SingletonLock to prevent "profile already in use" crashes
    lock_file = Path(CHROME_PROFILE_DIR) / "SingletonLock"
    lock_file.unlink(missing_ok=True)

    pw = sync_playwright().start()
    context = pw.chromium.launch_persistent_context(
        CHROME_PROFILE_DIR,
        channel="chrome",
        headless=False,
        args=["--disable-gpu"],
    )
    page = context.pages[0] if context.pages else context.new_page()
    page.set_default_timeout(E2E_TIMEOUT_MS)
    page.set_default_navigation_timeout(E2E_TIMEOUT_MS)

    # Navigate to the app — lands on /login
    page.goto(base_url)
    page.wait_for_load_state("domcontentloaded")

    # Click Google sign-in button — Google cookies in the profile
    # auto-complete the OAuth flow and redirect back with a token
    google_btn = page.locator("#g_id_signin")
    google_btn.wait_for(state="visible")
    google_btn.click()

    # Wait for OAuth redirect to complete and land on an authenticated page
    page.wait_for_url("**/chat**", timeout=E2E_TIMEOUT_MS)

    yield page

    context.close()
    pw.stop()
