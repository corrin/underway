"""Playwright e2e test fixtures — uses real Chrome profile with Google auth.

Prerequisites:
- Full stack running: backend on :9000, frontend, ngrok (BASE_URL).
- BASE_URL + PLAYWRIGHT_CHROME_PROFILE set (in .env / .env.test).
- Your real Chrome must be CLOSED — the persistent profile can't be shared, and a
  headful launch against a locked profile crashes (SIGTRAP).
- These tests use SYNC Playwright. pytest-asyncio's auto mode and pytest-playwright
  both inject a running event loop that breaks sync_playwright, so run via
  `scripts/run-e2e.sh` (it passes `-p no:asyncio -p no:playwright`).

Some tests need a connected, task-enabled Google account (see `google_tasks_account`).
"""

import asyncio
import contextlib
import os
import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
from dotenv import find_dotenv, load_dotenv
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from playwright.sync_api import Page, sync_playwright
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from underway.config import get_settings
from underway.models.external_account import ExternalAccount

load_dotenv(find_dotenv())  # BASE_URL etc. — shared with the app
load_dotenv(find_dotenv(".env.test"))  # test-only creds — kept out of Settings

# Global Playwright timeout — no individual timeout should exceed this.
E2E_TIMEOUT_MS = 10000

# Chrome profile with saved Google session.
# To set up: google-chrome --user-data-dir=<path>
# Then log into Google and close the browser.
# Add PLAYWRIGHT_CHROME_PROFILE=<path> to backend/.env.test
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

    # Navigate to the app — router redirects to /login if no token, /chat otherwise
    page.goto(base_url)
    page.wait_for_load_state("domcontentloaded")

    if "/login" in page.url:
        # No cached JWT — click Google sign-in. Google cookies in the profile
        # auto-complete the OAuth flow and redirect back with a token.
        google_btn = page.locator("#g_id_signin")
        google_btn.wait_for(state="visible")
        google_btn.click()
        page.wait_for_url("**/chat**", timeout=E2E_TIMEOUT_MS)
    else:
        # Already authenticated from a prior run — JWT is still valid in localStorage
        pass

    yield page

    context.close()
    pw.stop()


async def _load_google_tasks_account() -> tuple[str, str | None, str | None] | None:
    """Read a connected, task-enabled Google account from the app DB, or None."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            result = await session.execute(
                select(ExternalAccount).where(
                    ExternalAccount.provider == "google",
                    ExternalAccount.use_for_tasks.is_(True),
                    ExternalAccount.needs_reauth.is_(False),
                )
            )
            account = result.scalars().first()
            if account is None:
                return None
            return account.external_email, account.token, account.refresh_token
    finally:
        await engine.dispose()


class GoogleTasksSandbox:
    """Creates sentinel tasks in a real Google Tasks account and cleans them all up."""

    def __init__(self, email: str, service: object) -> None:
        self.email = email
        self.service = service
        self._created_ids: list[str] = []

    def create(self, title: str) -> str:
        task = self.service.tasks().insert(tasklist="@default", body={"title": title}).execute()
        task_id: str = task["id"]
        self._created_ids.append(task_id)
        return task_id

    def update_title(self, task_id: str, title: str) -> None:
        self.service.tasks().patch(tasklist="@default", task=task_id, body={"title": title}).execute()

    def delete(self, task_id: str) -> None:
        self.service.tasks().delete(tasklist="@default", task=task_id).execute()
        if task_id in self._created_ids:
            self._created_ids.remove(task_id)
        else:
            pass

    def cleanup(self) -> None:
        for task_id in list(self._created_ids):
            with contextlib.suppress(Exception):
                self.service.tasks().delete(tasklist="@default", task=task_id).execute()


@pytest.fixture
def google_tasks(base_url: str) -> Generator[GoogleTasksSandbox]:
    """A real Google Tasks sandbox for the connected, task-enabled Google account.

    Skips if no such account is connected — set one up once via Settings (re-auth Google,
    then click "Use for tasks"). Any sentinel tasks created are deleted on teardown.
    """
    account = asyncio.run(_load_google_tasks_account())
    if account is None:
        pytest.skip(
            "No task-enabled Google account connected. In Settings, re-auth Google "
            "(grants the tasks scope) then click 'Use for tasks' before running this test."
        )
    else:
        pass

    email, token, refresh_token = account
    settings = get_settings()
    creds = Credentials(
        token=token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scopes=["https://www.googleapis.com/auth/tasks"],
    )
    service = build("tasks", "v1", credentials=creds)
    sandbox = GoogleTasksSandbox(email, service)
    yield sandbox
    sandbox.cleanup()


def unique_sentinel() -> str:
    """A unique task title so stale rows can never cause a false pass."""
    return f"E2E-SYNC-{uuid.uuid4()}"
