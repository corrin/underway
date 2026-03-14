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

# Trace output directory
TRACE_DIR = Path("/tmp/e2e-results")


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

    # Check if already authenticated — the nav bar only renders when logged in.
    if page.locator(aid("nav-logout-button")).count() == 0:
        # Not logged in — perform Google OAuth via the GSI button.
        # The button lives inside a cross-origin iframe in #g_id_signin.
        # Use frame_locator() to reach inside — clicking the iframe element
        # from outside doesn't work with CDP.
        gsi_container = page.locator(aid("login-google-signin"))
        gsi_frame = gsi_container.frame_locator("iframe")
        gsi_button = gsi_frame.locator("div[role='button']")
        gsi_button.wait_for(state="visible", timeout=OAUTH_TIMEOUT_MS)

        with page.expect_navigation(wait_until="commit", timeout=OAUTH_TIMEOUT_MS):
            gsi_button.click()

        # Now on Google's account chooser. Select the target account.
        account_item = page.locator("text=lakeland@gmail.com")
        account_item.wait_for(state="visible", timeout=OAUTH_TIMEOUT_MS)

        with page.expect_navigation(wait_until="commit", timeout=OAUTH_TIMEOUT_MS):
            account_item.first.click()

        # Wait for the full redirect chain to land back on our app at /chat.
        page.wait_for_url("**/chat**", wait_until="domcontentloaded", timeout=OAUTH_TIMEOUT_MS)

    page.close()

    yield context

    browser.close()
    chrome_proc.send_signal(signal.SIGTERM)
    chrome_proc.wait(timeout=5)


@pytest.fixture
def authenticated_page(
    request: pytest.FixtureRequest,
    authenticated_context: BrowserContext,
) -> Generator[Page]:
    """New tab from the authenticated session context, closed after each test.

    Captures a Playwright trace for every test. Traces are saved to
    /tmp/e2e-results/<test-name>/trace.zip — open with:
        npx playwright show-trace /tmp/e2e-results/<test-name>/trace.zip
    """
    page = authenticated_context.new_page()
    page.set_default_timeout(E2E_TIMEOUT_MS)
    page.set_default_navigation_timeout(E2E_TIMEOUT_MS)

    # Start tracing for this test
    test_name = request.node.name.replace("/", "-").replace("::", "-")
    authenticated_context.tracing.start(screenshots=True, snapshots=True)

    yield page

    # Save trace regardless of pass/fail
    trace_path = TRACE_DIR / test_name
    trace_path.mkdir(parents=True, exist_ok=True)
    authenticated_context.tracing.stop(path=str(trace_path / "trace.zip"))
    page.close()
