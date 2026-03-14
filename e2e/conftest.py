"""Playwright e2e test fixtures.

Unauthenticated tests use pytest-playwright's built-in `page` fixture
(gives --headed, --browser, etc. for free).

Authenticated tests use a persistent Chrome profile with saved Google session.
Chrome is launched as a subprocess and connected via CDP, because
launch_persistent_context + system Chrome crashes on WSL2 with
"Browser window not found".

Prerequisites: Full Stack must be running (backend, frontend, ngrok).
"""

import os
import shutil
import signal
import subprocess
import time
from collections.abc import Generator
from pathlib import Path

import pytest
from dotenv import load_dotenv
from playwright.sync_api import BrowserContext, Page, Playwright

# Load env from the backend .env file
load_dotenv(Path(__file__).resolve().parent.parent / "backend" / ".env")

# Global Playwright timeout — no individual timeout should exceed this.
E2E_TIMEOUT_MS = 10_000

# Generous timeout for OAuth redirects that traverse external providers.
OAUTH_TIMEOUT_MS = 30_000

# Chrome profile with saved Google session.
CHROME_PROFILE_DIR = os.environ.get("PLAYWRIGHT_CHROME_PROFILE", "")

# Base URL for the app — must go through ngrok, never localhost.
BASE_URL = os.environ.get("BASE_URL", "")


def aid(value: str) -> str:
    """Return a CSS selector for data-automation-id."""
    return f"[data-automation-id='{value}']"


@pytest.fixture(scope="session")
def base_url() -> str:
    """App base URL (ngrok)."""
    if not BASE_URL:
        pytest.skip("BASE_URL is not set in backend/.env")
    return BASE_URL


CDP_PORT = 9223  # Avoid conflict with any manually-launched Chrome on 9222


@pytest.fixture(scope="session")
def authenticated_context(
    playwright: Playwright,
    base_url: str,
) -> Generator[BrowserContext]:
    """Persistent browser context with real Google auth via Chrome profile.

    Launches Chrome as a subprocess with --remote-debugging-port and connects
    via CDP.  This avoids launch_persistent_context which crashes on WSL2 with
    system Chrome ("Browser window not found").
    """
    if not CHROME_PROFILE_DIR:
        pytest.skip("PLAYWRIGHT_CHROME_PROFILE is not set in backend/.env")

    chrome_bin = shutil.which("google-chrome") or shutil.which("google-chrome-stable")
    if not chrome_bin:
        pytest.skip("google-chrome not found on PATH")

    # Remove stale SingletonLock to prevent "profile already in use" crashes
    lock_file = Path(CHROME_PROFILE_DIR) / "SingletonLock"
    lock_file.unlink(missing_ok=True)

    # Launch Chrome with the real profile and CDP enabled
    chrome_proc = subprocess.Popen(
        [
            chrome_bin,
            f"--user-data-dir={CHROME_PROFILE_DIR}",
            f"--remote-debugging-port={CDP_PORT}",
            "--no-sandbox",
            "--disable-gpu",
            "--disable-extensions",
            "--no-first-run",
            "--no-default-browser-check",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for CDP to be ready
    browser = None
    for _ in range(30):
        try:
            browser = playwright.chromium.connect_over_cdp(
                f"http://127.0.0.1:{CDP_PORT}"
            )
            break
        except Exception:
            time.sleep(0.5)

    if browser is None:
        chrome_proc.kill()
        pytest.fail("Chrome did not start with CDP in time")

    context = browser.contexts[0]

    # Perform Google login once for the session — use generous timeouts for
    # ngrok tunneling + Google OAuth redirects during setup.
    page = context.pages[0] if context.pages else context.new_page()
    page.set_default_timeout(OAUTH_TIMEOUT_MS)
    page.set_default_navigation_timeout(OAUTH_TIMEOUT_MS)

    page.goto(base_url, wait_until="networkidle")
    page.screenshot(path="/tmp/e2e_01_landing.png")

    # The Google Sign-In button is a cross-origin iframe inside #g_id_signin.
    # Click the iframe element directly so the click reaches Google's button.
    gsi_container = page.locator(aid("login-google-signin"))
    gsi_iframe = gsi_container.locator("iframe")
    gsi_iframe.wait_for(state="visible")

    # Get the iframe bounding box and click at its center coordinates on the
    # page level — this avoids cross-origin iframe click issues with CDP.
    box = gsi_iframe.bounding_box()
    if box:
        page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)

    # Wait a moment, then screenshot to see where we are
    page.wait_for_timeout(3000)
    page.screenshot(path="/tmp/e2e_02_after_click.png")

    # Log the current URL for debugging
    current_url = page.url
    print(f"URL after GSI click: {current_url}")

    # If we're on the Google account chooser, select the account
    if "accounts.google.com" in current_url:
        account_item = page.locator("text=lakeland@gmail.com")
        account_item.wait_for(state="visible", timeout=OAUTH_TIMEOUT_MS)
        account_item.first.click()

    # Wait for the full redirect chain to land back on our app.
    page.wait_for_url("**/chat**", wait_until="domcontentloaded", timeout=OAUTH_TIMEOUT_MS)
    page.screenshot(path="/tmp/e2e_03_authenticated.png")
    page.close()

    yield context

    browser.close()
    chrome_proc.send_signal(signal.SIGTERM)
    chrome_proc.wait(timeout=5)


@pytest.fixture
def authenticated_page(
    authenticated_context: BrowserContext,
) -> Generator[Page]:
    """New tab from the authenticated session context, closed after each test."""
    page = authenticated_context.new_page()
    page.set_default_timeout(E2E_TIMEOUT_MS)
    page.set_default_navigation_timeout(E2E_TIMEOUT_MS)

    yield page

    page.close()
