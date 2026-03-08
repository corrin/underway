"""Playwright e2e test fixtures."""

import os
import subprocess
import time
from collections.abc import Generator

import pytest


@pytest.fixture(scope="session")
def backend_server() -> Generator[str, None, None]:
    """Start the backend server for e2e tests with TESTING=true."""
    backend_dir = os.path.join(os.path.dirname(__file__), "..", "..")
    proc = subprocess.Popen(
        [".venv/bin/python", "-m", "uvicorn", "aligned.app:create_app", "--factory", "--port", "8091"],
        cwd=backend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={
            **os.environ,
            "TESTING": "true",
        },
    )
    time.sleep(2)
    yield "http://localhost:8091"
    proc.terminate()
    proc.wait()


@pytest.fixture(scope="session")
def frontend_server() -> Generator[str, None, None]:
    """Start the frontend dev server for e2e tests on a dedicated port."""
    frontend_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "frontend")
    port = "5191"
    proc = subprocess.Popen(
        ["npx", "vite", "--port", port, "--strictPort"],
        cwd=frontend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(3)
    yield f"http://localhost:{port}"
    proc.terminate()
    proc.wait()


@pytest.fixture
def authenticated_page(
    backend_server: str,
    frontend_server: str,
    page: "pytest.Page",  # type: ignore[name-defined]
) -> "pytest.Page":  # type: ignore[name-defined]
    """Page with a valid JWT token in localStorage, bypassing Google OAuth."""
    response = page.request.post(
        f"{backend_server}/api/auth/test-login",
        data={"email": "e2e-test@example.com"},
    )
    assert response.ok, f"test-login failed: {response.status}"
    token = response.json()["token"]
    # Navigate to frontend first so localStorage is on the right origin
    page.goto(frontend_server)
    page.evaluate(f"localStorage.setItem('token', '{token}')")
    # Reload so the Vue router picks up the token from localStorage
    page.reload()
    page.wait_for_load_state("networkidle")
    return page
