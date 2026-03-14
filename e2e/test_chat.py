"""E2E smoke tests for the chat page."""

import pytest
from playwright.sync_api import Page

from conftest import aid


@pytest.mark.e2e
def test_chat_page_loads(base_url: str, authenticated_page: Page) -> None:
    """Chat page loads with input field and sidebar."""
    authenticated_page.goto(f"{base_url}/chat")
    textarea = authenticated_page.locator(aid("chat-message-input"))
    textarea.wait_for(state="visible")
    assert textarea.is_visible()


@pytest.mark.e2e
def test_chat_has_new_chat_button(base_url: str, authenticated_page: Page) -> None:
    """New Chat button is visible on the chat page."""
    authenticated_page.goto(f"{base_url}/chat")
    new_btn = authenticated_page.locator(aid("chat-new-button"))
    new_btn.wait_for(state="visible")
    assert new_btn.is_visible()


@pytest.mark.e2e
def test_chat_has_dashboard_sidebar(base_url: str, authenticated_page: Page) -> None:
    """Dashboard sidebar is visible on the chat page."""
    authenticated_page.goto(f"{base_url}/chat")
    sidebar = authenticated_page.locator(".chat-sidebar--right")
    sidebar.wait_for(state="visible")
    assert sidebar.is_visible()
