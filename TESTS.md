# Test Coverage Reference

Three test layers cover the Web Extraction Manager. Run them with:

```bash
pytest tests/unit tests/integration   # 94 tests, ~1 s
pytest tests/e2e                       # 37 tests, ~30 s
```

---

## Summary

| Layer | File(s) | Test items | Run time |
|---|---|---|---|
| Unit | `tests/unit/test_credit_service.py` | 11 | < 1 s |
| Unit | `tests/unit/test_job_service.py` | 41 | < 1 s |
| Integration | `tests/integration/test_credits_api.py` | 7 | < 1 s |
| Integration | `tests/integration/test_jobs_api.py` | 35 | < 1 s |
| E2E | `tests/e2e/test_ui.py` | 37 | ~30 s |
| **Total** | | **131** | |

> Parametrized tests expand the item count beyond the number of `def test_*` functions. For example, `test_raises_invalid_url_error_for_bad_url` is one function but runs as 8 separate test items.

---

## Unit Tests

Unit tests call service functions directly — no HTTP, no Flask, no browser. The `reset_store` autouse fixture in `tests/conftest.py` wipes in-memory state before every test.

### `tests/unit/test_credit_service.py` — 11 tests

#### `TestGetCredits`
| Test | What it covers |
|---|---|
| `test_new_user_gets_default_credits` | A user who has never been seen is initialised with `DEFAULT_CREDITS` (100). |
| `test_existing_user_returns_current_balance` | A user with a pre-set balance returns that balance, not the default. |

#### `TestHasCredits`
| Test | What it covers |
|---|---|
| `test_has_credits_true_when_positive` | Returns `True` when balance > 0. |
| `test_has_credits_false_at_zero` | Returns `False` at exactly 0 — the boundary condition that blocks job starts. |
| `test_new_user_has_credits` | A brand-new user passes the credit check (initialised at 100). |

#### `TestDeductCredit`
| Test | What it covers |
|---|---|
| `test_deduct_reduces_balance_by_one` | Each call subtracts exactly 1. |
| `test_deduct_returns_new_balance` | Return value is the post-deduction balance. |
| `test_deduct_multiple_times` | Three sequential deductions from 10 → 7. |
| `test_deduct_does_not_go_below_zero` | Calling deduct when balance is already 0 leaves it at 0. |
| `test_deduct_from_one_reaches_zero_not_negative` | Boundary: deducting from 1 results in exactly 0, not −1. |

#### `TestCreditsNotRestoredOnStop`
| Test | What it covers |
|---|---|
| `test_credits_unchanged_after_stop` | Stopping a running job never refunds credits — the business rule that credits are consumed, not loaned. |

---

### `tests/unit/test_job_service.py` — 41 tests

#### `TestRegisterJob`
| Test | What it covers |
|---|---|
| `test_returns_pending_job` | Newly registered job has status `pending`, correct owner and URL. |
| `test_assigns_unique_ids` | Two jobs registered in sequence receive different UUIDs. |
| `test_job_stored_in_store` | Job appears in the in-memory store after registration. |
| `test_pages_processed_starts_at_zero` | Counter is 0 at registration — no pages consumed yet. |
| `test_raises_invalid_url_error_for_bad_url` _(×8 parametrized)_ | `InvalidUrlError` is raised for: bare string, scheme-less domain, `ftp://`, `javascript:`, scheme-relative `//`, relative path, `https://` with no host, empty string. |
| `test_accepts_valid_http_and_https_urls` _(×5 parametrized)_ | Valid `http://` and `https://` URLs with paths, ports, query strings, and fragments are accepted. |
| `test_invalid_url_is_not_stored` | A rejected URL leaves the store empty — no partial state is written. |

#### `TestListJobs`
| Test | What it covers |
|---|---|
| `test_returns_jobs_for_user` | Lists jobs belonging to the requested user. |
| `test_excludes_other_users_jobs` | Another user's jobs are not included — basic data isolation. |
| `test_empty_for_unknown_user` | Returns an empty list for a user with no jobs. |

#### `TestStartJob`
| Test | What it covers |
|---|---|
| `test_transitions_to_running` | `start_job` immediately sets status to `running` before the simulation thread completes. |
| `test_raises_if_job_not_found` | `JobNotFoundError` on an unknown job ID. |
| `test_raises_when_no_credits` | `InsufficientCreditsError` when the user's credit balance is 0. |
| `test_raises_when_user_limit_reached` | `UserJobLimitError` when the user already has `USER_MAX_JOBS` running. |
| `test_raises_when_system_limit_reached` | `SystemJobLimitError` when the total running count reaches `SYSTEM_MAX_JOBS`. |
| `test_raises_when_already_running` | `ValueError` when trying to start a job that is already running. |

#### `TestSimulation`
| Test | What it covers |
|---|---|
| `test_completes_after_simulation` | The background thread sets status to `completed` after it finishes. |
| `test_increments_pages_processed` | `pages_processed` goes from 0 to 1 after simulation. |
| `test_deducts_one_credit_per_page` | Exactly 1 credit is deducted from the owner's balance. |

#### `TestStopJob`
| Test | What it covers |
|---|---|
| `test_transitions_running_job_to_stopped` | `stop_job` changes status from `running` to `stopped`. |
| `test_raises_when_stopping_pending_job` | `ValueError` when trying to stop a job that was never started. |
| `test_raises_if_job_not_found` | `JobNotFoundError` on an unknown job ID. |
| `test_stop_does_not_reverse_credits` | Credit balance is unchanged after stopping — no refund. |

#### `TestDeleteJob`
| Test | What it covers |
|---|---|
| `test_removes_job_from_store` | Deleted job is absent from the store. |
| `test_raises_if_job_not_found` | `JobNotFoundError` on an unknown job ID. |
| `test_can_delete_pending_job` | `pending` jobs can be deleted. |
| `test_can_delete_stopped_job` | `stopped` jobs can be deleted. |
| `test_can_delete_completed_job` | `completed` jobs can be deleted. |
| `test_deleting_running_job_stops_thread_and_removes_job` | Deleting a `running` job sets status to `stopped` first (so the background thread aborts cleanly) then removes it from the store. |
| `test_delete_does_not_affect_other_jobs` | Deleting one job leaves sibling jobs untouched. |

---

## Integration Tests

Integration tests exercise the full HTTP request/response cycle using Flask's test client. Service functions are mocked where needed so each test targets a single layer: routing, request parsing, response serialization, and error-to-status-code mapping.

### `tests/integration/test_credits_api.py` — 7 tests

#### `TestGetCredits` — `GET /api/credits`
| Test | What it covers |
|---|---|
| `test_returns_200` | Successful request returns HTTP 200. |
| `test_response_contains_credits_field` | Response JSON includes a `credits` key with the balance. |
| `test_response_contains_user_id_field` | Response JSON echoes back the `user_id`. |
| `test_calls_service_with_user_id` | Endpoint passes the query-param `user_id` to the service. |
| `test_reflects_reduced_balance` | A non-default balance (e.g. 57) is serialised correctly. |
| `test_reflects_zero_balance` | Zero balance is serialised as `0`, not omitted or `null`. |
| `test_missing_user_id_returns_400` | Omitting `?user_id=` returns HTTP 400. |

---

### `tests/integration/test_jobs_api.py` — 35 tests

#### `TestCreateJob` — `POST /api/jobs`
| Test | What it covers |
|---|---|
| `test_returns_201` | Successful registration returns HTTP 201 Created. |
| `test_response_contains_job_fields` | Response includes `id`, `owner`, `url`, `status`, `pages_processed`. |
| `test_calls_service_with_correct_args` | Endpoint forwards `user_id` and `url` to `register_job`. |
| `test_missing_url_returns_400` | Body without `url` returns HTTP 400. |
| `test_missing_user_id_returns_400` | Body without `user_id` returns HTTP 400. |
| `test_empty_body_returns_400` | Empty JSON body `{}` returns HTTP 400. |
| `test_invalid_url_returns_400` _(×5 parametrized)_ | Invalid URLs (`notaurl`, `ftp://`, `//`, `https://`, `/relative`) return HTTP 400. |
| `test_invalid_url_response_contains_error_message` | Response body for an invalid URL includes an `error` key. |

#### `TestListJobs` — `GET /api/jobs`
| Test | What it covers |
|---|---|
| `test_returns_200` | Returns HTTP 200 for a valid request. |
| `test_returns_list_of_jobs` | Response is a JSON array; job fields are serialised correctly. |
| `test_calls_service_with_user_id` | `?user_id=` query param is forwarded to `list_jobs`. |
| `test_missing_user_id_returns_400` | Omitting `?user_id=` returns HTTP 400. |
| `test_empty_list_when_no_jobs` | Returns `[]` when the service returns no jobs. |

#### `TestStartJob` — `POST /api/jobs/<id>/start`
| Test | What it covers |
|---|---|
| `test_returns_200` | Successful start returns HTTP 200. |
| `test_response_shows_running_status` | Response JSON has `"status": "running"`. |
| `test_calls_service_with_job_id` | URL path segment is passed to `start_job`. |
| `test_job_not_found_returns_404` | `JobNotFoundError` → HTTP 404. |
| `test_no_credits_returns_402` | `InsufficientCreditsError` → HTTP 402 Payment Required. |
| `test_user_limit_returns_409` | `UserJobLimitError` → HTTP 409 Conflict. |
| `test_system_limit_returns_409` | `SystemJobLimitError` → HTTP 409 Conflict. |
| `test_invalid_state_returns_409` | `ValueError` (e.g. already running) → HTTP 409 Conflict. |

#### `TestStopJob` — `POST /api/jobs/<id>/stop`
| Test | What it covers |
|---|---|
| `test_returns_200` | Successful stop returns HTTP 200. |
| `test_response_shows_stopped_status` | Response JSON has `"status": "stopped"`. |
| `test_calls_service_with_job_id` | URL path segment is passed to `stop_job`. |
| `test_job_not_found_returns_404` | `JobNotFoundError` → HTTP 404. |
| `test_job_not_running_returns_409` | `ValueError` (job not running) → HTTP 409 Conflict. |

#### `TestDeleteJob` — `DELETE /api/jobs/<id>`
| Test | What it covers |
|---|---|
| `test_returns_204` | Successful deletion returns HTTP 204 No Content. |
| `test_response_body_is_empty` | 204 response has no body. |
| `test_calls_service_with_job_id` | URL path segment is passed to `delete_job`. |
| `test_job_not_found_returns_404` | `JobNotFoundError` → HTTP 404. |
| `test_job_not_found_response_contains_error` | 404 response body includes an `error` key. |

---

## E2E Tests

E2E tests drive a real Chromium browser via Playwright against a live Flask subprocess. The server starts once per session. Each test uses the `isolated_page` fixture, which sets `currentOperator` to a unique generated ID before the test body runs — guaranteeing 100 credits and an empty job list with no server reset required.

`TestPageLoad` is the only class that uses the plain `page` fixture, intentionally testing the raw default state of the application.

### `tests/e2e/test_ui.py` — 37 tests

#### `TestPageLoad`
| Test | What it covers |
|---|---|
| `test_page_title` | Browser tab title is "Web Extraction Manager". |
| `test_main_heading_visible` | `<h1>` text matches the app name. |
| `test_operator_dropdown_has_five_options` | Dropdown is populated with exactly 5 operators on load. |
| `test_default_operator_is_alice` | Default selected operator is alice. |
| `test_credit_balance_loads_on_startup` | Credit balance is fetched and displayed (not `—`) on page load. |
| `test_empty_state_shown_when_no_jobs` | Empty-state message is visible and the table is hidden when the operator has no jobs. |

#### `TestRegisterJob`
| Test | What it covers |
|---|---|
| `test_empty_url_shows_validation_error` | Submitting the form with no URL shows "Please enter a URL" in the message area. |
| `test_empty_url_does_not_create_a_job` | The empty-state message remains visible — no job is created. |
| `test_register_shows_success_banner` | A valid submission shows a green "Job registered successfully" banner. |
| `test_url_input_cleared_after_register` | The URL input is cleared after a successful registration. |
| `test_registered_job_appears_in_table` | The jobs table becomes visible with one row after registration. |
| `test_registered_job_shows_correct_url` | The registered URL is displayed in the table row. |
| `test_registered_job_has_pending_status` | Newly registered job shows status badge `pending`. |
| `test_pending_job_start_enabled_stop_disabled` | For a pending job, Start is enabled and Stop is disabled. |
| `test_multiple_jobs_each_get_own_row` | Registering two jobs produces two table rows. |

#### `TestStartJob`
| Test | What it covers |
|---|---|
| `test_start_job_reaches_completed_status` | Clicking Start eventually shows status `completed` (via the 2-second poll). |
| `test_start_job_decrements_credit_balance` | After completion, credit balance decreases from 100 to 99. |
| `test_start_job_increments_pages_processed` | Pages processed counter shows 1 after a completed job. |
| `test_completed_job_both_buttons_disabled` | Both Start and Stop are disabled for a completed job. |

#### `TestStopJob`
| Test | What it covers |
|---|---|
| `test_running_job_has_stop_enabled_start_disabled` | When a job is `running`, Stop is enabled and Start is disabled. Uses route interception to freeze the status at `running` without relying on the 100 ms simulation window. |
| `test_clicking_stop_sends_stop_request` | Clicking Stop fires `POST /api/jobs/<id>/stop` and the response has `"status": "stopped"`. Both GET and POST routes are mocked to test UI wiring without timing dependencies. |
| `test_stopped_job_shows_stopped_status_badge` | A job stopped via API shows the amber `stopped` badge in the UI after Refresh. |
| `test_stopped_job_both_buttons_disabled` | Both Start and Stop are disabled for a stopped job. |
| `test_stopped_job_pages_not_decremented_on_stop` | A job stopped before simulation completes shows 0 pages processed — credits are not reversed. |

#### `TestDeleteJob`
| Test | What it covers |
|---|---|
| `test_delete_button_present_on_every_row` | Each job row renders a Delete button. |
| `test_clicking_delete_shows_inline_confirmation` | Clicking Delete replaces the button with Confirm and Cancel in-line — no browser dialog. |
| `test_cancel_restores_original_buttons` | Clicking Cancel restores the original Delete button. |
| `test_confirm_removes_job_row` | Clicking Confirm removes the job row from the table. |
| `test_confirm_shows_empty_state_when_last_job_deleted` | Deleting the last job shows the empty-state message. |
| `test_deleting_one_job_leaves_others_intact` | Deleting job B leaves job A's row visible. |

#### `TestOperatorIsolation`
| Test | What it covers |
|---|---|
| `test_switching_operator_shows_empty_list` | Jobs registered under operator A are not visible when switching to operator B. |
| `test_switching_operator_updates_credit_display` | After operator A spends a credit (99), switching to a fresh operator B shows 100. |
| `test_switching_back_restores_previous_operator_jobs` | Switching A → B → A restores operator A's job list. |
| `test_each_operator_has_independent_credits` | Two fresh operators both show 100 credits independently. |
| `test_dropdown_switch_isolates_jobs` | Switching via the actual HTML dropdown (not JS) correctly isolates data. |

#### `TestRefreshButton`
| Test | What it covers |
|---|---|
| `test_refresh_picks_up_api_registered_job` | A job created via the API (not the UI form) appears in the list after clicking Refresh. |
| `test_refresh_shows_updated_status` | Refresh reflects a status change: job moves from `pending` to `completed` between two Refresh clicks. |

---

## What is not covered by automated tests

| Area | Reason |
|---|---|
| Concurrent credit deduction race condition | The read-modify-write in `credit_service.deduct_credit` is not thread-safe; no concurrency test verifies this. |
| `USER_MAX_JOBS` / `SYSTEM_MAX_JOBS` at zero or negative values | Config boundary values below the normal operating range are not tested. |
| Ownership enforcement on start/stop/delete | No check prevents user A from operating on user B's job — a service-layer gap. |
| Whitespace-only URL input | `"   "` is truthy and passes the API's `if not url` guard; the service's URL validator catches it, but no test covers this specific input at the API layer. |
| E2E: `running` status badge | The simulation completes in 100 ms, making the transient `running` state unreachable through normal UI interaction. Covered at unit and integration layers. |

---

## Testing Metrics

### Code Coverage

Coverage is measured against the application source (`app/`) excluding the static UI file, which is JavaScript and not instrumented by Python's coverage tools.

**Run coverage for the service layer (highest value — all business logic lives here):**

```bash
pytest tests/unit --cov=app/services --cov-report=term-missing
```

**Run coverage for the full application (services + API):**

```bash
pytest tests/unit tests/integration --cov=app --cov-report=term-missing
```

**Minimum thresholds:**

| Layer | Minimum line coverage | Why |
|---|---|---|
| `app/services/` | 90% | All credit rules, job lifecycle, and limit enforcement live here. Gaps here mean untested business logic. |
| `app/api/` | 85% | All endpoints and error mappings are exercised by integration tests. |
| `app/models/` | 80% | Dataclass and store; logic-light but still measured. |

To enforce thresholds in CI, add `--cov-fail-under=<n>` to the pytest invocation. The overall combined threshold across `app/services` and `app/api` should be at least **88%** before shipping.

### Pass Rate

**100% pass rate is required** — no failures, no errors. Skipped tests are not permitted in the main suite unless a skip has an explicit documented reason (`@pytest.mark.skip(reason="...")`).

### Test Execution Time Budget

Slow tests are a signal that isolation or test design has regressed.

| Suite | Budget | Action if exceeded |
|---|---|---|
| Unit + integration | < 5 s | Investigate mocking — something may be hitting real I/O |
| E2E | < 90 s | Profile individual tests; consider whether setup fixtures are doing too much |

---

## Release Criteria

A release is considered ready for public deployment when **all five gates below are satisfied**. No gate can be waived without explicit sign-off and a documented risk acceptance.

---

### Gate 1 — All Automated Tests Pass

Run the full suite with no failures, errors, or unexpected skips:

```bash
pytest tests/unit tests/integration tests/e2e
```

Expected output: `131 passed`.

---

### Gate 2 — Coverage Thresholds Met

```bash
pytest tests/unit tests/integration \
  --cov=app/services --cov=app/api --cov=app/models \
  --cov-report=term-missing \
  --cov-fail-under=88
```

The command must exit with code 0. A failing coverage check blocks the release.

---

### Gate 3 — Critical Business Rules Individually Verified

The following tests are individually named as release-blocking. Passing the overall suite is necessary but not sufficient; these specific tests must be in the passing set, because each one guards a business rule that would cause financial or data correctness harm if broken.

| Business rule | Blocking tests |
|---|---|
| Zero credits blocks job start | `test_raises_when_no_credits` · `test_has_credits_false_at_zero` · `test_no_credits_returns_402` |
| Per-user concurrent job cap enforced | `test_raises_when_user_limit_reached` · `test_user_limit_returns_409` |
| System-wide concurrent job cap enforced | `test_raises_when_system_limit_reached` · `test_system_limit_returns_409` |
| Credits are consumed, not refunded on stop | `test_stop_does_not_reverse_credits` · `test_credits_unchanged_after_stop` · `test_stopped_job_pages_not_decremented_on_stop` |
| Malformed URLs are rejected before storage | `test_raises_invalid_url_error_for_bad_url` (×8) · `test_invalid_url_is_not_stored` · `test_invalid_url_returns_400` (×5) |
| Operator data isolation | `test_excludes_other_users_jobs` · `TestOperatorIsolation` (×5 E2E tests) |
| Deleting a running job stops its thread cleanly | `test_deleting_running_job_stops_thread_and_removes_job` |
| Only pending jobs can be started | `test_raises_when_already_running` · `test_invalid_state_returns_409` |

Run these in isolation to confirm they pass without relying on suite-wide state:

```bash
pytest tests/unit tests/integration -k "no_credits or user_limit or system_limit or reverse_credits or invalid_url or excludes_other or deleting_running or already_running" -v
```

---

### Gate 4 — E2E Golden Path Verified

The end-to-end operator workflow must complete successfully in a headless Chromium browser. This gate confirms that the API, server startup, and UI are correctly wired together — something no unit or integration test can verify.

The exact sequence that must pass:

1. Server starts and serves `index.html` at `/`
2. Dropdown populates with 5 operators; credit balance loads (not `—`)
3. Register a job by entering a URL — row appears with `pending` status, URL input clears, success banner shown
4. Click Start — status eventually shows `completed`; credit balance decrements by 1; pages processed shows 1; both buttons disabled
5. Register a second job; click Delete — inline confirmation appears; click Confirm — row removed; empty state shown if no jobs remain
6. Switch operator via dropdown — job list and credit balance update to reflect the new operator's state

These steps are covered by the automated E2E suite. Gate 4 is satisfied when `pytest tests/e2e` reports all 37 tests passing. For a deployment against an external server (staging), run:

```bash
pytest tests/e2e --server-url=<staging-url>
```

---

### Gate 5 — No Open P0 or P1 Defects

No blocker or critical defect may be open at release time. The severity scale is defined relative to this project's specific failure modes:

| Severity | Definition | Examples for this project |
|---|---|---|
| **P0 — Blocker** | Data integrity failure, security failure, or system unusable. Release is stopped. | Credits deducted with no job started; operator A can read or modify operator B's jobs; server returns 500 on valid input; job stuck permanently in `running` with no thread |
| **P1 — Critical** | Core feature broken with no viable workaround. | Job limit not enforced; credit balance displayed wrong; state transition produces wrong status; delete does not remove the job |
| **P2 — Major** | Feature impaired but a workaround exists. Document and plan fix for next release. | UI shows stale status after start/stop without manual refresh; delete confirmation buttons do not appear; start button enabled for a non-pending job |
| **P3 — Minor** | Cosmetic or edge-case UX issue. No blocking impact. | Error message wording unclear; status badge colour does not match the style guide; layout breaks at very narrow window widths |

P2 defects must have a documented workaround and a committed fix date. P3 defects may be deferred to a backlog.

---

### Release Checklist Summary

| # | Gate | How to verify | Blocking |
|---|---|---|---|
| 1 | All 131 tests pass | `pytest tests/unit tests/integration tests/e2e` → `131 passed` | Yes |
| 2 | Coverage ≥ 88% on services + API | `pytest tests/unit tests/integration --cov=app --cov-fail-under=88` exits 0 | Yes |
| 3 | Critical business rule tests individually pass | Named test filter (see above) | Yes |
| 4 | E2E golden path passes against target server | `pytest tests/e2e [--server-url=<target>]` → `37 passed` | Yes |
| 5 | No open P0 or P1 defects | Manual defect triage | Yes |
