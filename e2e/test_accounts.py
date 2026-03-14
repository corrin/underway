"""E2E tests for account management — connect and disconnect external providers.

Each test deletes any existing account for the target provider/email,
connects via OAuth, and verifies the account appears in the settings table.

Requires: Full Stack running (backend, frontend, ngrok) and a Chrome profile
with saved sessions for Google, O365, and Todoist.
"""

import pytest
from playwright.sync_api import Page, expect

from conftest import OAUTH_TIMEOUT_MS, aid


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def delete_account_if_exists(page: Page, email: str, provider: str) -> None:
    """Find a table row by email AND provider, click Delete, confirm modal."""
    # Use provider label + email to uniquely identify the row
    rows = page.locator(".accounts-table tbody tr")
    count = rows.count()
    for i in range(count):
        row = rows.nth(i)
        row_text = row.inner_text()
        if email in row_text and provider in row_text:
            # Found the row — click its delete button
            row.locator(".btn-delete").click()

            # Confirm in the modal
            modal_delete = page.locator(aid("settings-delete-confirm"))
            modal_delete.wait_for(state="visible")
            modal_delete.click()

            # Wait for the page to reload accounts (modal closes)
            page.locator(aid("settings-delete-modal")).wait_for(
                state="detached", timeout=OAUTH_TIMEOUT_MS
            )
            # Give the API time to process and re-render
            page.wait_for_timeout(1000)
            return


def click_oauth_account_if_picker(page: Page, email: str) -> None:
    """If an OAuth provider shows an account picker, click the target email."""
    # Give the redirect chain a moment to settle
    page.wait_for_timeout(2000)
    # If we're on an external OAuth domain with a picker, select the account
    url = page.url
    if "accounts.google.com" in url or "login.microsoftonline.com" in url:
        picker = page.locator(f"text={email}")
        if picker.count() > 0:
            picker.first.click(timeout=OAUTH_TIMEOUT_MS)


def wait_for_oauth_complete(page: Page, base_url: str) -> None:
    """Wait for the OAuth redirect chain to land back on /settings."""
    page.wait_for_url(f"{base_url}/settings**", wait_until="domcontentloaded", timeout=OAUTH_TIMEOUT_MS)


def verify_account_row(page: Page, email: str, provider_label: str) -> None:
    """Assert that a row with the given email and provider exists and is Active."""
    row = page.locator(f".accounts-table tbody tr:has(.col-email:text-is('{email}'))")
    # Filter to the row that also contains the provider label
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
    page = authenticated_page
    email = "lakeland@gmail.com"

    page.goto(f"{base_url}/settings")
    page.locator("h1").wait_for(state="visible")

    delete_account_if_exists(page, email, "Google")

    page.locator(aid("settings-connect-google")).click()
    click_oauth_account_if_picker(page, email)
    wait_for_oauth_complete(page, base_url)

    verify_account_row(page, email, "Google")


@pytest.mark.e2e
def test_add_google_account_morris(
    base_url: str, authenticated_page: Page
) -> None:
    """Connect Google account corrin@morrissheetmetal.co.nz via OAuth."""
    page = authenticated_page
    email = "corrin@morrissheetmetal.co.nz"

    page.goto(f"{base_url}/settings")
    page.locator("h1").wait_for(state="visible")

    delete_account_if_exists(page, email, "Google")

    page.locator(aid("settings-connect-google")).click()
    click_oauth_account_if_picker(page, email)
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
    page = authenticated_page
    email = "corrin.lakeland@cmeconnect.com"

    page.goto(f"{base_url}/settings")
    page.locator("h1").wait_for(state="visible")

    delete_account_if_exists(page, email, "Microsoft")

    page.locator(aid("settings-connect-microsoft")).click()
    click_oauth_account_if_picker(page, email)
    wait_for_oauth_complete(page, base_url)

    verify_account_row(page, email, "Microsoft 365")


# ---------------------------------------------------------------------------
# Todoist account
# ---------------------------------------------------------------------------


@pytest.mark.e2e
def test_add_todoist_account(
    base_url: str, authenticated_page: Page
) -> None:
    """Connect Todoist account via OAuth."""
    page = authenticated_page

    page.goto(f"{base_url}/settings")
    page.locator("h1").wait_for(state="visible")

    delete_account_if_exists(page, "lakeland@gmail.com", "Todoist")

    page.locator(aid("settings-connect-todoist")).click()

    wait_for_oauth_complete(page, base_url)

    # Verify a Todoist row appeared with Active status
    todoist_row = page.locator(".accounts-table tbody tr").filter(has_text="Todoist")
    expect(todoist_row).to_be_visible(timeout=OAUTH_TIMEOUT_MS)
    expect(todoist_row.locator(".status-badge")).to_contain_text("Active")
