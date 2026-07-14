# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a take-home assignment to build a **Web Extraction Manager** — a small internal service where an operator can register web extraction jobs, view them, and start or stop them. Each job draws against a monthly page credit allowance for the account.

**Stack:** Any stack is acceptable; in-memory storage is fine.

**Deliverables:**
- Simple web UI: register a job, list jobs, start/stop a job
- Tests (see strategy below)
- `STRATEGY.md` explaining testing decisions

## Architecture

Client/server application:

- **Client:** Browser-based web UI (the UI layer)
- **Server:** REST API layer — handles job CRUD, start/stop, and tracks monthly credit usage per user

The API layer is the heart of the system. Business logic must be encapsulated in **services** invoked by the API endpoints, so core logic can be unit tested directly without going through HTTP.

## Business Rules

- `USER_MAX_JOBS`: Max concurrent jobs a single user can run
- `SYSTEM_MAX_JOBS`: Max concurrent jobs across all users
- Starting a new job checks both limits before proceeding
- One credit is deducted per page processed
- Credits are **not reversed** when a job is stopped
- If a user has zero credits remaining, they cannot start a new job
- **No persistent storage** — all state is in-memory

## Testing Strategy

Three layers:

1. **Unit tests** — test services directly (no HTTP). Cover credit deduction, job limit enforcement, state transitions.
2. **Integration tests** — test the API endpoints end-to-end (HTTP requests against the running server in test mode).
3. **E2E tests** — browser-driven smoke tests of the UI layer, including data isolation checks.

Highest-risk areas: concurrent job limit enforcement (race conditions on `SYSTEM_MAX_JOBS`), credit boundary conditions (exactly 0 credits), and job state transitions (start/stop sequencing).

## Setup

```bash
# Activate the virtual environment (Windows)
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers (first time only)
playwright install chromium
```

## Running the App and Tests

`pytest.ini` sets `pythonpath = .` so the `app` package is importable without any extra setup. Always run pytest from the project root.

```bash
# Run the development server
python run.py

# Swagger UI (interactive API docs) — available while the server is running
# http://127.0.0.1:5000/apidocs/   — UI
# http://127.0.0.1:5000/apispec.json — raw OpenAPI spec

# Run all tests (unit + integration)
pytest tests/unit tests/integration

# Run E2E tests — server starts and stops automatically, no manual setup needed
pytest tests/e2e

# Run E2E tests in headed mode (visible browser window, useful for debugging)
pytest tests/e2e --headed

# Run E2E tests with slow motion (500 ms between actions, useful for watching)
pytest tests/e2e --headed --slowmo=500

# Run E2E tests with an HTML report (open playwright-report/index.html afterwards)
pytest tests/e2e --headed --html=playwright-report/index.html --self-contained-html

# Run a single test file
pytest tests/unit/test_job_service.py

# Check test coverage (shows which lines are not covered)
pytest tests/unit --cov=app --cov-report=term-missing

# Generate an HTML coverage report (open htmlcov/index.html in a browser)
pytest tests/unit --cov=app --cov-report=html

# --- Reporting ---

# JUnit XML — consumed by GitHub Actions, GitLab CI, Jenkins, Azure DevOps
pytest tests/unit --junit-xml=reports/junit.xml

# HTML test report — human-readable, single self-contained file
pytest tests/unit --html=reports/test-report.html --self-contained-html

# All-in-one: JUnit XML + HTML report + coverage (typical CI run)
pytest tests/unit --junit-xml=reports/junit.xml --html=reports/test-report.html --self-contained-html --cov=app --cov-report=xml:reports/coverage.xml --cov-report=html
```

## E2E Test Architecture

E2E tests live in `tests/e2e/` and use **pytest-playwright** (Chromium, headless by default).

### Server lifecycle

`tests/e2e/conftest.py` manages everything automatically:

- **`live_server` (session-scoped)** — spawns `python run.py` as a subprocess at the start of the session, polls `GET /` until it responds, then kills the process after all tests finish. Do **not** start the server manually before running E2E tests.
- **`base_url` (session-scoped)** — passes `http://127.0.0.1:5000` to pytest-playwright so `page.goto("/")` resolves correctly.
- **`reset_server` (function-scoped, autouse)** — calls `POST /api/reset` before every test to wipe the in-memory store. This is what provides data isolation between tests.

### Reset endpoint

`POST /api/reset` is registered in `create_app()` (`app/__init__.py`). It calls `store.reset()`, which marks any running jobs as stopped (so background threads exit cleanly) and then clears all jobs and credits. This endpoint exists solely for test isolation — there is no auth on it since the project has no auth layer.

### Stop-button test approach

The job simulation completes in 100 ms, making it impossible to race a UI click to the stop endpoint reliably. The two stop-click tests (`TestStopJob`) use `page.route()` to intercept network calls:

- GET `/api/jobs?*` is mocked to return the job as `"running"` so the Stop button renders enabled.
- POST `/api/jobs/<id>/stop` is mocked to return `"stopped"` so the click handler gets a clean response.

This tests the UI wiring (button state → API call → response handling) without depending on server timing. The real stop transition (`running → stopped`) is proven by the integration tests.

### Selectors used

All Playwright selectors target IDs and `data-testid` attributes defined in `app/static/index.html`:

