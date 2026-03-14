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


def delete_account_if_exists(page: Page, email: str) -> None:
    """Find a table row by email, click Delete, confirm the modal, wait for removal."""
    row = page.locator(f".accounts-table tbody tr:has(.col-email:text-is('{email}'))")
    if row.count() == 0:
        return

    row.locator(aid("settings-account-delete") if False else ".btn-delete").click()

    # Confirm in the modal
    modal_delete = page.locator(aid("settings-delete-confirm"))
    modal_delete.wait_for(state="visible")
    modal_delete.click()

    # Wait for the row to disappear
    row.wait_for(state="detached", timeout=OAUTH_TIMEOUT_MS)


def wait_for_oauth_complete(page: Page, base_url: str) -> None:
    """Wait for the OAuth redirect chain to land back on /settings."""
    page.wait_for_url(f"{base_url}/settings**", timeout=OAUTH_TIMEOUT_MS)
    page.wait_for_load_state("domcontentloaded")


def verify_account_row(page: Page, email: str, provider_label: str) -> None:
    """Assert that a row with the given email and provider exists and is Active."""
    row = page.locator(f".accounts-table tbody tr:has(.col-email:text-is('{email}'))")
    expect(row).to_be_visible(timeout=OAUTH_TIMEOUT_MS)
    expect(row).to_contain_text(provider_label)
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

    delete_account_if_exists(page, email)

    page.locator(aid("settings-connect-google")).click()

    # Google may show an account picker — select the target email
    picker_item = page.locator(f"text={email}")
    if picker_item.count() > 0:
        picker_item.first.click(timeout=OAUTH_TIMEOUT_MS)

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

    delete_account_if_exists(page, email)

    page.locator(aid("settings-connect-google")).click()

    picker_item = page.locator(f"text={email}")
    if picker_item.count() > 0:
        picker_item.first.click(timeout=OAUTH_TIMEOUT_MS)

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

    delete_account_if_exists(page, email)

    page.locator(aid("settings-connect-microsoft")).click()

    # Microsoft may show an account picker
    picker_item = page.locator(f"text={email}")
    if picker_item.count() > 0:
        picker_item.first.click(timeout=OAUTH_TIMEOUT_MS)

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

    # For Todoist we don't know the exact email ahead of time,
    # so we check if any Todoist row exists and delete it first.
    todoist_row = page.locator(".accounts-table tbody tr:has(td:text-is('Todoist'))")
    if todoist_row.count() > 0:
        todoist_row.first.locator(".btn-delete").click()
        modal_delete = page.locator(aid("settings-delete-confirm"))
        modal_delete.wait_for(state="visible")
        modal_delete.click()
        todoist_row.first.wait_for(state="detached", timeout=OAUTH_TIMEOUT_MS)

    page.locator(aid("settings-connect-todoist")).click()

    wait_for_oauth_complete(page, base_url)

    # Verify a Todoist row appeared with Active status
    todoist_row = page.locator(".accounts-table tbody tr:has(td:text-is('Todoist'))")
    expect(todoist_row).to_be_visible(timeout=OAUTH_TIMEOUT_MS)
    expect(todoist_row.locator(".status-badge")).to_contain_text("Active")
