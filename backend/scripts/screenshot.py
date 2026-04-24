"""
Take screenshots of URLs using the user's authenticated Chrome session.

Usage:
    python -m scripts.screenshot https://underway-lakeland.ngrok.io/chat
    python -m scripts.screenshot https://example.com --output /tmp/shot.png
    python -m scripts.screenshot https://example.com --full-page
"""

import argparse
import time
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

from scripts.browser import connect_to_chrome


def take_screenshot(url: str, output: str | None = None, full_page: bool = False, wait: float = 2.0) -> str:
    """Take a screenshot of a URL and return the output path."""
    if output is None:
        hostname = urlparse(url).hostname or "page"
        path_part = urlparse(url).path.strip("/").replace("/", "_") or "index"
        output = f"/tmp/screenshot_{hostname}_{path_part}.png"

    pw = sync_playwright().start()
    try:
        _browser, context, _ = connect_to_chrome(playwright=pw)
        page = context.new_page()
        page.goto(url, wait_until="networkidle")
        time.sleep(wait)  # Extra wait for JS-rendered content
        page.screenshot(path=output, full_page=full_page)
        page.close()
        print(f"Screenshot saved to {output}")
        return output
    finally:
        pw.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Take screenshots via Chrome CDP")
    parser.add_argument("url", help="URL to screenshot")
    parser.add_argument("--output", "-o", help="Output file path (default: /tmp/screenshot_<host>_<path>.png)")
    parser.add_argument("--full-page", action="store_true", help="Capture full scrollable page")
    parser.add_argument("--wait", type=float, default=2.0, help="Seconds to wait after page load (default: 2)")
    args = parser.parse_args()

    take_screenshot(args.url, args.output, args.full_page, args.wait)


if __name__ == "__main__":
    main()
