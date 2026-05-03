"""Take a screenshot of a route in the running app via Playwright.

Usage:
    poetry run python scripts/screenshot.py [route] [--out path] [--width N] [--height N]

Defaults: route=/chat, out=/tmp/underway_screen.png, viewport=1920x1080.

Reuses the same Chrome profile and BASE_URL as the e2e tests
(PLAYWRIGHT_CHROME_PROFILE in backend/.env.test, BASE_URL in backend/.env).
"""
import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from login import login

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / "backend" / ".env")
load_dotenv(REPO_ROOT / "backend" / ".env.test")

PROFILE = os.environ.get("PLAYWRIGHT_CHROME_PROFILE", "")
BASE_URL = os.environ.get("BASE_URL", "")
USER_EMAIL = os.environ.get("GOOGLE_TEST_EMAIL", "")
TIMEOUT_MS = 10000

_missing = [
    name
    for name, value in (
        ("PLAYWRIGHT_CHROME_PROFILE (backend/.env.test)", PROFILE),
        ("BASE_URL (backend/.env)", BASE_URL),
        ("GOOGLE_TEST_EMAIL (backend/.env.test)", USER_EMAIL),
    )
    if not value
]
if _missing:
    sys.exit(f"Missing env: {', '.join(_missing)}")
else:
    pass

parser = argparse.ArgumentParser()
parser.add_argument("route", nargs="?", default="/chat")
parser.add_argument("--out", default="/tmp/underway_screen.png")
parser.add_argument("--width", type=int, default=1920)
parser.add_argument("--height", type=int, default=1080)
args = parser.parse_args()

(Path(PROFILE) / "SingletonLock").unlink(missing_ok=True)

with sync_playwright() as pw:
    context = pw.chromium.launch_persistent_context(
        PROFILE,
        channel="chrome",
        headless=False,
        viewport={"width": args.width, "height": args.height},
        args=["--disable-gpu", f"--window-size={args.width},{args.height}"],
    )
    page = context.pages[0] if context.pages else context.new_page()
    page.set_default_timeout(TIMEOUT_MS)
    page.set_default_navigation_timeout(TIMEOUT_MS)

    page.goto(f"{BASE_URL}{args.route}")
    page.wait_for_load_state("networkidle")
    if "/login" in page.url:
        login(page, USER_EMAIL, args.route)
    else:
        pass

    page.screenshot(path=args.out, full_page=False)
    print(f"URL:      {page.url}")
    print(f"Viewport: {page.viewport_size}")
    print(f"Saved:    {args.out}")
    context.close()
