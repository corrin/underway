"""E2E smoke tests for the calendar page."""

import pytest
from playwright.sync_api import Page

from conftest import aid


@pytest.mark.e2e
def test_calendar_page_loads(base_url: str, authenticated_page: Page) -> None:
    """Calendar page loads with heading."""
    authenticated_page.goto(f"{base_url}/calendar")
    heading = authenticated_page.locator("h1")
    heading.wait_for(state="visible")
    assert heading.inner_text() == "Calendar"


@pytest.mark.e2e
def test_calendar_shows_events_section(base_url: str, authenticated_page: Page) -> None:
    """Calendar page has an events section."""
    authenticated_page.goto(f"{base_url}/calendar")
    events_heading = authenticated_page.locator("h2", has_text="Upcoming Events")
    events_heading.wait_for(state="visible")
    assert events_heading.is_visible()
