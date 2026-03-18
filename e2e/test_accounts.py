"""E2E tests for account management — connect and disconnect external providers.

Each test deletes any existing account for the target provider/email,
connects via OAuth (filling in credentials on provider login pages),
and verifies the account appears in the settings table.

Requires: Full Stack running (backend, frontend, ngrok) and test credentials
in backend/.env (GOOGLE_TEST_EMAIL, GOOGLE_TEST_PASSWORD, O365_TEST_EMAIL,
O365_TEST_PASSWORD, TODOIST_TEST_EMAIL).
"""

import os

import pytest
from playwright.sync_api import Page, expect

from conftest import OAUTH_TIMEOUT_MS, aid


# ---------------------------------------------------------------------------
# Test credentials from .env
# ---------------------------------------------------------------------------

GOOGLE_TEST_EMAIL = os.environ.get("GOOGLE_TEST_EMAIL", "")
GOOGLE_TEST_EMAIL_2 = os.environ.get("GOOGLE_TEST_EMAIL_2", "")
GOOGLE_TEST_PASSWORD = os.environ.get("GOOGLE_TEST_PASSWORD", "")
O365_TEST_EMAIL = os.environ.get("O365_TEST_EMAIL", "")
O365_TEST_PASSWORD = os.environ.get("O365_TEST_PASSWORD", "")
TODOIST_TEST_EMAIL = os.environ.get("TODOIST_TEST_EMAIL", "")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def delete_account_if_exists(page: Page, email: str, provider: str) -> None:
    """Find a table row by email AND provider, click Delete, confirm modal."""
    rows = page.locator(".accounts-table tbody tr")
    count = rows.count()
    for i in range(count):
        row = rows.nth(i)
        row_text = row.inner_text()
        if email in row_text and provider in row_text:
            row.locator(".btn-delete").click()

            modal_delete = page.locator(aid("settings-delete-confirm"))
            modal_delete.wait_for(state="visible")
            modal_delete.click()

            page.locator(aid("settings-delete-modal")).wait_for(
                state="detached", timeout=OAUTH_TIMEOUT_MS
            )
            page.wait_for_timeout(1000)
            return


def _wait_visible(page: Page, selector: str, timeout: int = 5000) -> bool:
    """Poll for selector to become visible within timeout. Returns True if found."""
    interval = 500
    elapsed = 0
    loc = page.locator(selector).first
    while elapsed < timeout:
        if loc.is_visible():
            return True
        page.wait_for_timeout(interval)
        elapsed += interval
    return False


def handle_google_oauth(page: Page, email: str, password: str) -> None:
    """Handle Google's OAuth login/consent flow.

    Google may show: account chooser, login form, or consent/warning page.
    The Chrome profile may already have a session, in which case Google
    may skip some steps.
    """
    page.wait_for_timeout(3000)

    if "accounts.google.com" not in page.url:
        return

    # Step 1: Identify — account chooser OR email input
    if _wait_visible(page, f"text={email}", timeout=3000):
        page.locator(f"text={email}").first.click()
        page.wait_for_timeout(2000)
    elif _wait_visible(page, "input[type='email']", timeout=3000):
        page.locator("input[type='email']").first.fill(email)
        page.locator("#identifierNext").first.click()
        page.wait_for_timeout(3000)
    else:
        print(f"OAuth: unexpected — no account chooser or email input (url={page.url})")
        return

    # Step 2: Password — may be skipped if session already has credentials
    if "accounts.google.com" not in page.url:
        return
    if _wait_visible(page, "input[type='password']", timeout=3000):
        page.locator("input[type='password']").first.fill(password)
        page.locator("#passwordNext").first.click()
        page.wait_for_timeout(3000)
    else:
        print(f"OAuth: no password field, session may have credentials (url={page.url})")

    # Step 3: Consent / warning page — click "Continue" or "Allow"
    for _ in range(5):
        if "accounts.google.com" not in page.url:
            break
        if _wait_visible(page, "button:has-text('Continue')", timeout=2000):
            page.locator("button:has-text('Continue')").first.click()
            page.wait_for_timeout(2000)
        elif _wait_visible(page, "button:has-text('Allow')", timeout=2000):
            page.locator("button:has-text('Allow')").first.click()
            page.wait_for_timeout(2000)
        else:
            print(f"OAuth: stuck on google, no Continue/Allow found (url={page.url})")
            break


def handle_o365_oauth(page: Page, email: str, password: str) -> None:
    """Handle Microsoft O365 OAuth login flow."""
    page.wait_for_timeout(3000)

    if "microsoftonline.com" not in page.url and "login.live.com" not in page.url:
        return

    # Step 1: Email — may be skipped if session already has it
    if _wait_visible(page, "input[name='loginfmt']", timeout=5000):
        page.locator("input[name='loginfmt']").first.fill(email)
        page.locator("input[type='submit']").first.click()
        page.wait_for_timeout(3000)
    else:
        print(f"OAuth: no email input on O365, session may have it (url={page.url})")

    # Step 2: Password — may be skipped if session already has credentials
    if _wait_visible(page, "input[name='passwd']", timeout=5000):
        page.locator("input[name='passwd']").first.fill(password)
        page.locator("input[type='submit']").first.click()
        page.wait_for_timeout(3000)
    else:
        print(f"OAuth: no password field on O365, session may have it (url={page.url})")

    # Step 3: "Stay signed in?" — optional
    if _wait_visible(page, "input[type='submit'][value='Yes']", timeout=5000):
        page.locator("input[type='submit'][value='Yes']").first.click()
        page.wait_for_timeout(2000)

    # Step 4: Consent — optional
    if _wait_visible(page, "input[type='submit'][value='Accept']", timeout=3000):
        page.locator("input[type='submit'][value='Accept']").first.click()
        page.wait_for_timeout(2000)


def handle_todoist_oauth(page: Page, google_email: str, google_password: str) -> None:
    """Handle Todoist OAuth flow — Todoist login page, then 'Continue with Google'."""
    page.wait_for_timeout(3000)

    if "todoist.com" not in page.url:
        return

    # Todoist shows its own login page — click "Continue with Google"
    if _wait_visible(page, "a:has-text('Continue with Google')", timeout=5000):
        page.locator("a:has-text('Continue with Google')").first.click()
    elif _wait_visible(page, "button:has-text('Continue with Google')", timeout=3000):
        page.locator("button:has-text('Continue with Google')").first.click()
    elif _wait_visible(page, "[data-testid='google-login']", timeout=3000):
        page.locator("[data-testid='google-login']").first.click()
    else:
        print(f"OAuth: no Google login option on Todoist page (url={page.url})")
        return
    page.wait_for_timeout(3000)

    # Now we're in Google's OAuth flow for Todoist
    handle_google_oauth(page, google_email, google_password)


def wait_for_oauth_complete(page: Page, base_url: str) -> None:
    """Wait for the OAuth redirect chain to land back on /settings."""
    page.wait_for_url(f"{base_url}/settings**", wait_until="domcontentloaded", timeout=OAUTH_TIMEOUT_MS)


def verify_account_row(page: Page, email: str, provider_label: str) -> None:
    """Assert that a row with the given email and provider exists and is Active."""
    row = page.locator(f".accounts-table tbody tr:has(.col-email:text-is('{email}'))")
    row = row.filter(has_text=provider_label)
    expect(row).to_be_visible(timeout=OAUTH_TIMEOUT_MS)
    expect(row.locator(".status-badge")).to_contain_text("Active")


# ---------------------------------------------------------------------------
# Google accounts
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_add_google_account_lakeland(
    base_url: str, authenticated_page: Page
) -> None:
    """Connect Google account lakeland@gmail.com via OAuth."""
    if not GOOGLE_TEST_PASSWORD:
        pytest.skip("GOOGLE_TEST_PASSWORD not set in backend/.env")

    page = authenticated_page
    email = GOOGLE_TEST_EMAIL or "lakeland@gmail.com"

    page.goto(f"{base_url}/settings")
    page.locator("h1").wait_for(state="visible")

    delete_account_if_exists(page, email, "Google")

    page.locator(aid("settings-connect-google")).click()
    handle_google_oauth(page, email, GOOGLE_TEST_PASSWORD)
    wait_for_oauth_complete(page, base_url)

    verify_account_row(page, email, "Google")


@pytest.mark.e2e
def test_add_google_account_morris(
    base_url: str, authenticated_page: Page
) -> None:
    """Connect Google account corrin@morrissheetmetal.co.nz via OAuth."""
    if not GOOGLE_TEST_PASSWORD:
        pytest.skip("GOOGLE_TEST_PASSWORD not set in backend/.env")

    page = authenticated_page
    email = GOOGLE_TEST_EMAIL_2 or "corrin@morrissheetmetal.co.nz"

    page.goto(f"{base_url}/settings")
    page.locator("h1").wait_for(state="visible")

    delete_account_if_exists(page, email, "Google")

    page.locator(aid("settings-connect-google")).click()
    handle_google_oauth(page, email, GOOGLE_TEST_PASSWORD)
    wait_for_oauth_complete(page, base_url)

    verify_account_row(page, email, "Google")


# ---------------------------------------------------------------------------
# O365 account
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_add_o365_account(
    base_url: str, authenticated_page: Page
) -> None:
    """Connect O365 account corrin.lakeland@cmeconnect.com via OAuth."""
    if not O365_TEST_PASSWORD:
        pytest.skip("O365_TEST_PASSWORD not set in backend/.env")

    page = authenticated_page
    email = O365_TEST_EMAIL or "corrin.lakeland@cmeconnect.com"

    page.goto(f"{base_url}/settings")
    page.locator("h1").wait_for(state="visible")

    delete_account_if_exists(page, email, "Microsoft")

    page.locator(aid("settings-connect-microsoft")).click()
    handle_o365_oauth(page, email, O365_TEST_PASSWORD)
    wait_for_oauth_complete(page, base_url)

    verify_account_row(page, email, "Microsoft 365")


# ---------------------------------------------------------------------------
# Todoist account
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_add_todoist_account(
    base_url: str, authenticated_page: Page
) -> None:
    """Connect Todoist account via OAuth (signs in with Google)."""
    if not GOOGLE_TEST_PASSWORD:
        pytest.skip("GOOGLE_TEST_PASSWORD not set in backend/.env")

    page = authenticated_page
    todoist_email = TODOIST_TEST_EMAIL or "lakeland@gmail.com"

    page.goto(f"{base_url}/settings")
    page.locator("h1").wait_for(state="visible")

    delete_account_if_exists(page, todoist_email, "Todoist")

    page.locator(aid("settings-connect-todoist")).click()
    handle_todoist_oauth(page, todoist_email, GOOGLE_TEST_PASSWORD)
    wait_for_oauth_complete(page, base_url)

    todoist_row = page.locator(".accounts-table tbody tr").filter(has_text="Todoist")
    expect(todoist_row).to_be_visible(timeout=OAUTH_TIMEOUT_MS)
    expect(todoist_row.locator(".status-badge")).to_contain_text("Active")
