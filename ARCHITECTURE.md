# System Architecture

## Overview

Web Extraction Manager is a single-server, browser-based application. An operator selects their identity from a dropdown, registers extraction jobs by URL, and starts, stops, or deletes them. Each started job runs a short simulation that consumes one page credit from the operator's monthly allowance.

All state is held in memory. There is no database, no authentication, and no persistence across server restarts.

---

## Technology Stack

| Concern | Choice |
|---|---|
| Language | Python 3.12 |
| Web framework | Flask 3.x |
| UI | Plain HTML / CSS / JavaScript (no framework) |
| Browser automation (E2E) | Playwright (pytest-playwright) |
| Test runner | pytest |
| HTTP client (integration tests) | Flask test client (in-process) |

---

## Directory Structure

```
.
├── run.py                        # Entry point — creates app and starts dev server
├── pytest.ini                    # pythonpath = . so `app` is importable
├── requirements.txt
│
├── app/
│   ├── __init__.py               # create_app() factory; registers blueprints and root route
│   ├── config.py                 # Runtime constants (USER_MAX_JOBS, SYSTEM_MAX_JOBS, DEFAULT_CREDITS)
│   │
│   ├── models/
│   │   ├── job.py                # Job dataclass
│   │   └── store.py              # Module-level in-memory store + reset()
│   │
│   ├── services/
│   │   ├── job_service.py        # All job business logic; domain exceptions
│   │   └── credit_service.py     # Credit read / check / deduct
│   │
│   ├── api/
│   │   ├── jobs.py               # Jobs Blueprint — 5 endpoints
│   │   └── credits.py            # Credits Blueprint — 1 endpoint
│   │
│   └── static/
│       └── index.html            # Single-page application (HTML + CSS + JS in one file)
│
└── tests/
    ├── conftest.py               # reset_store autouse fixture (unit + integration)
    ├── unit/
    │   ├── test_credit_service.py
    │   └── test_job_service.py
    ├── integration/
    │   ├── conftest.py           # Flask test client fixtures
    │   ├── test_credits_api.py
    │   └── test_jobs_api.py
    └── e2e/
        ├── conftest.py           # Live server + operator isolation fixtures
        └── test_ui.py
```

---

## Application Layers

The system is strictly layered. Each layer communicates only with the layer directly below it.

```
Browser (SPA)
    │  fetch()
    ▼
API Layer  (Flask Blueprints)
    │  function calls
    ▼
Service Layer
    │  direct access
    ▼
In-Memory Store
```

### 1. Configuration — `app/config.py`

Three module-level constants. No environment variable override mechanism exists.

| Constant | Value | Meaning |
|---|---|---|
| `USER_MAX_JOBS` | 3 | Maximum concurrent `running` jobs per operator |
| `SYSTEM_MAX_JOBS` | 10 | Maximum concurrent `running` jobs across all operators |
| `DEFAULT_CREDITS` | 100 | Credits assigned to an operator the first time they are seen |

---

### 2. Data Model — `app/models/`

#### `Job` (`app/models/job.py`)

A `@dataclass` with no methods beyond `__post_init__`.

| Field | Type | Default | Notes |
|---|---|---|---|
| `id` | `str` | required | UUID string, generated at registration |
| `owner` | `str` | required | Operator user ID |
| `url` | `str` | required | Validated absolute http/https URL |
| `status` | `str` | `"pending"` | One of `pending`, `running`, `stopped`, `completed` |
| `pages_processed` | `int` | `0` | Incremented by the simulation thread |
| `_thread` | — | `None` | Non-dataclass attribute; holds the `threading.Thread` reference |

#### `store` (`app/models/store.py`)

A plain module — not a class. Two module-level dicts act as the single source of truth.

```python
jobs: dict    # job_id (str) → Job
credits: dict # user_id (str) → int balance
```

`store.reset()` marks any `running` jobs as `stopped` before clearing both dicts. This signals active simulation threads to abort rather than writing to a cleared store.

---

### 3. Service Layer — `app/services/`

All business logic lives here. No HTTP concern crosses this boundary.

#### `credit_service.py`

| Function | Behaviour |
|---|---|
| `get_credits(user_id)` | Returns balance, initialising to `DEFAULT_CREDITS` on first call for a new user. |
| `has_credits(user_id)` | Returns `True` if balance > 0. |
| `deduct_credit(user_id)` | Subtracts 1, floors at 0, returns the new balance. |

Credit initialisation is lazy — a user only appears in `store.credits` after their first credit operation.

#### `job_service.py`

**Domain exceptions** defined here and imported by the API layer:

| Exception | Raised when |
|---|---|
| `InvalidUrlError` | URL does not have an `http`/`https` scheme and a non-empty netloc |
| `JobNotFoundError` | Job ID absent from `store.jobs` |
| `InsufficientCreditsError` | `has_credits()` returns `False` at start time |
| `UserJobLimitError` | User already has `USER_MAX_JOBS` running jobs |
| `SystemJobLimitError` | Total running jobs across all users equals `SYSTEM_MAX_JOBS` |

**Public functions:**

`register_job(user_id, url)` — Validates the URL with `urllib.parse.urlparse` (rejects anything that is not an absolute `http`/`https` URL), creates a `Job` with a new UUID, stores it, and returns it. Raises `InvalidUrlError` before touching the store.

`list_jobs(user_id)` — Returns all jobs in `store.jobs` whose `owner` matches.

`start_job(job_id)` — Enforces pre-conditions in order: status must be `pending` → user must have credits → user must be below `USER_MAX_JOBS` → system must be below `SYSTEM_MAX_JOBS`. On success, sets status to `running`, starts a daemon thread running `_simulate`, and returns the job immediately (the thread runs concurrently).

`stop_job(job_id)` — Requires status `running`; sets it to `stopped`. The simulation thread detects this on its next status check and returns without processing pages.

`delete_job(job_id)` — If the job is `running`, sets status to `stopped` first (clean thread abort), then removes it from `store.jobs`. Works for any status.

**Simulation thread — `_simulate(job)`:**

```
wait 100 ms (threading.Event, not time.sleep — patchable in tests)
if job.status != "running":
    return  ← aborted by stop or delete
job.pages_processed += 1
deduct_credit(job.owner)
job.status = "completed"
```

`threading.Event().wait(timeout=0.1)` is used instead of `time.sleep(0.1)` because `time.sleep` is patched to a no-op in the unit tests (so the test thread can observe the `running` status between `start_job` returning and the thread completing). `threading.Event().wait` is unaffected by that patch.

---

### 4. API Layer — `app/api/`

Two Flask Blueprints registered in `create_app()`. The API's only job is to translate HTTP ↔ service calls: parse request inputs, call the appropriate service function, map exceptions to HTTP status codes, and serialise responses to JSON.

#### Job serialisation

Every job response uses `_serialize(job)`:

```json
{
  "id": "uuid-string",
  "owner": "alice",
  "url": "https://example.com/page",
  "status": "pending",
  "pages_processed": 0
}
```

#### Endpoints

| Method | Path | Success | Description |
|---|---|---|---|
| `GET` | `/` | 200 | Serves `app/static/index.html` |
| `POST` | `/api/jobs` | 201 | Register a new job |
| `GET` | `/api/jobs?user_id=` | 200 | List all jobs for an operator |
| `POST` | `/api/jobs/<id>/start` | 200 | Start a pending job |
| `POST` | `/api/jobs/<id>/stop` | 200 | Stop a running job |
| `DELETE` | `/api/jobs/<id>` | 204 | Delete a job (any status) |
| `GET` | `/api/credits?user_id=` | 200 | Get credit balance for an operator |

#### Error responses

All error responses are `{"error": "<message>"}` JSON except `DELETE /api/jobs/<id>` on success, which returns an empty 204 body.

| HTTP status | Meaning |
|---|---|
| 400 | Missing/invalid request field or malformed URL |
| 402 | Insufficient credits |
| 404 | Job ID not found |
| 409 | Invalid state transition or concurrent job limit reached |

---

### 5. UI Layer — `app/static/index.html`

A self-contained single-page application. HTML, CSS, and JavaScript are all in one file. No framework, no build step, no external dependencies.

#### Operator list

Five operators are hardcoded in JavaScript:
```javascript
const OPERATORS = ['alice', 'bob', 'carol', 'dave', 'eve'];
```

The API accepts any string as `user_id`, but the dropdown only surfaces these five.

#### State

Two module-level variables:
- `currentOperator` — the active user ID string
- `pollTimer` — `setTimeout` handle, or `null`

#### Data flow

```
Page load / operator change
  └─ loadAll()
       ├─ fetchCredits()  → GET /api/credits?user_id=<op>  → update #credit-balance
       └─ fetchJobs()     → GET /api/jobs?user_id=<op>     → renderJobs() → build table rows
            └─ schedulePoll(jobs)
                 └─ if any job.status === 'running':
                      setTimeout(poll, 2000)
                      poll() → fetchJobs() + fetchCredits() → schedulePoll()  [repeats]
```

Polling stops automatically when no jobs are in `running` status. It is cancelled and restarted on operator change.

#### Testability anchors

Every interactive element has a stable `id` and `data-testid` so Playwright selectors do not depend on layout or text:

| Element | `id` | `data-testid` |
|---|---|---|
| Operator dropdown | `operator-select` | — |
| Credit balance | `credit-balance` | — |
| URL input | `job-url-input` | — |
| Register button | `create-job-btn` | — |
| Refresh button | `refresh-jobs-btn` | — |
| Job status badge | `job-status-<id>` | `job-status-<id>` |
| Pages counter | `job-pages-<id>` | `job-pages-<id>` |
| Start button | `btn-start-<id>` | `btn-start-<id>` |
| Stop button | `btn-stop-<id>` | `btn-stop-<id>` |
| Delete button | `btn-delete-<id>` | `btn-delete-<id>` |
| Delete confirm | `btn-delete-confirm-<id>` | `btn-delete-confirm-<id>` |
| Delete cancel | `btn-delete-cancel-<id>` | `btn-delete-cancel-<id>` |

#### Delete confirmation

Clicking Delete does not use `window.confirm()` (which blocks browser events and breaks automation). Instead, clicking Delete swaps the actions cell inline: the Delete button is replaced by a "Delete this job?" label, a **Confirm** button, and a **Cancel** button. Confirm fires `DELETE /api/jobs/<id>`. Cancel calls `loadAll()` to restore the original row.

---

## Job State Machine

```
           register_job()
                │
                ▼
           ┌─────────┐
           │ pending  │
           └────┬────┘
                │ start_job()
                │ (checks: credits > 0,
                │  user < USER_MAX_JOBS,
                │  system < SYSTEM_MAX_JOBS)
                ▼
           ┌─────────┐
           │ running  │ ◄── simulation thread active
           └──┬──┬───┘
              │  │
    stop_job()│  │ simulation completes
     or       │  │ (100 ms)
  delete_job()│  │
              │  ▼
           ┌──▼──────┐     ┌───────────┐
           │ stopped  │     │ completed │
           └──────────┘     └───────────┘
```

All terminal states (stopped, completed) can be deleted. Running jobs can also be deleted; `delete_job` signals the thread to abort by setting status to `stopped` before removing the job from the store.

`start_job` only accepts `pending` jobs. Attempting to start a job in any other state raises `ValueError` → HTTP 409.

---

## Test Architecture

### Unit tests (`tests/unit/`)

Call service functions directly. The `reset_store` autouse fixture in `tests/conftest.py` calls `store.reset()` before each test. `time.sleep` is patched to a no-op where needed so tests do not wait for the 100 ms simulation.

### Integration tests (`tests/integration/`)

Use Flask's `app.test_client()` — no TCP socket, no subprocess. The client goes through the full Flask WSGI cycle (routing, request parsing, response serialisation) in-process. Service functions are mocked with `unittest.mock.patch` to test each HTTP error branch in isolation without manufacturing real error conditions.

### E2E tests (`tests/e2e/`)

Drive a real Chromium browser via Playwright.

**Server lifecycle:** `live_server` (session-scoped) spawns `python run.py` as a subprocess once for the whole session and terminates it at the end. Pass `--server-url=<URL>` to test against an already-running server instead.

**Test isolation:** No server reset between tests. Each test receives an `isolated_page` fixture that injects a unique generated operator ID (`op-<hex8>`) into the SPA's `currentOperator` variable before the test body runs. Because this user ID has never appeared in the in-memory store, it always starts with 100 credits and an empty job list. Credits are never shared between tests; jobs from one test are invisible to the next.

**Stop-button tests:** The job simulation completes in 100 ms, making the `running` status window too narrow to catch with UI clicks. Those tests use `page.route()` to intercept the GET `/api/jobs` response and inject `"status": "running"`, making the Stop button appear enabled without a real running job. The actual `running → stopped` transition is proven at the unit and integration layers.

---

## Known Design Limitations

| Area | Detail |
|---|---|
| No thread safety | `credit_service.deduct_credit` is a read-modify-write on a plain dict. Concurrent `start_job` calls can race past the `has_credits` check. |
| No ownership enforcement | Any operator can call `start_job`, `stop_job`, or `delete_job` on any job ID — there is no check that the caller owns the job. |
| Credits never reset | Once credits reach 0, the operator is permanently locked out with no mechanism to top up. |
| Hardcoded operator list | Adding a sixth operator requires editing JavaScript source. |
| No persistence | All state is lost on server restart. |
