import sys
import time
import uuid
import subprocess
import urllib.request
from pathlib import Path

import pytest

DEFAULT_URL = "http://127.0.0.1:5000"
PROJECT_ROOT = Path(__file__).parents[2]


def pytest_addoption(parser):
    parser.addoption(
        "--server-url",
        default=None,
        metavar="URL",
        help=(
            "Run E2E tests against an already-running server at URL "
            "(e.g. http://staging.example.com). "
            "When omitted, a local server is started automatically."
        ),
    )


def _wait_for_server(url: str, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return
        except Exception:
            time.sleep(0.15)
    raise RuntimeError(f"Server at {url} did not become ready within {timeout}s")


@pytest.fixture(scope="session")
def live_server(request):
    """
    Yield the base URL of the server under test.

    Default: spawn a local Flask subprocess once for the whole session and
    tear it down at the end.
    With --server-url: verify the external server is reachable and use it
    as-is; no process is started or stopped.
    """
    external = request.config.getoption("--server-url")

    if external:
        _wait_for_server(external)
        yield external
        return

    proc = subprocess.Popen(
        [sys.executable, "run.py"],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for_server(DEFAULT_URL)
        yield DEFAULT_URL
    finally:
        proc.terminate()
        proc.wait(timeout=5)


@pytest.fixture(scope="session")
def base_url(live_server):
    """Provide base_url to pytest-playwright so page.goto('/') works."""
    return live_server


@pytest.fixture
def operator():
    """
    A unique user ID for one test. Because the store is in-memory and this
    user has never been seen before, it always starts with 100 credits and
    an empty job list — no reset or cleanup required.
    """
    return f"op-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def isolated_page(page, live_server, operator):
    """
    Navigate to the app and switch currentOperator to the unique test
    operator. Tests using this fixture get a guaranteed clean slate
    (100 credits, 0 jobs) without any server-side reset.
    """
    page.goto(live_server)
    page.evaluate(f"currentOperator = '{operator}'; loadAll();")
    page.wait_for_function(
        "document.getElementById('credit-balance').textContent !== '—'"
    )
    return page
