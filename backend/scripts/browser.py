"""
Helper to connect Playwright to a user's Chrome instance via CDP (Chrome DevTools Protocol).

Requires Chrome to be running with --remote-debugging-port=9222 on the Windows host.
"""

import subprocess

from playwright.sync_api import Playwright, sync_playwright


def get_windows_host_ip() -> str:
    """Get the Windows host IP from WSL's default route."""
    result = subprocess.run(
        ["ip", "route", "show", "default"],
        capture_output=True,
        text=True,
        check=True,
    )
    # Output: "default via 172.x.x.x dev eth0"
    return result.stdout.strip().split()[2]


def connect_to_chrome(
    playwright: Playwright | None = None,
    port: int = 9222,
    save_state: bool = False,
    state_path: str = ".playwright-state.json",
) -> tuple:
    """
    Connect to Chrome via CDP.

    Returns (browser, context, owns_playwright) tuple.
    If playwright is None, creates its own instance (caller must stop it).
    """
    owns_playwright = playwright is None
    pw = sync_playwright().start() if owns_playwright else playwright

    host_ip = get_windows_host_ip()
    endpoint = f"http://{host_ip}:{port}"

    browser = pw.chromium.connect_over_cdp(endpoint)
    context = browser.contexts[0]  # Use the existing browser context (has cookies/auth)

    if save_state:
        context.storage_state(path=state_path)

    return browser, context, pw if owns_playwright else None
