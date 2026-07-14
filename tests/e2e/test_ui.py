"""
E2E tests for the Web Extraction Manager UI.

Isolation strategy
──────────────────
The server runs once for the whole session (session-scoped live_server).
Each test that creates or reads user-specific data uses the `isolated_page`
fixture, which sets currentOperator to a unique generated ID before the test
body runs. Because that user ID has never existed in the in-memory store, it
always starts with 100 credits and an empty job list — no server reset needed.

TestPageLoad is the only class that uses the plain `page` fixture directly;
those tests intentionally inspect the app's default state (operator = alice,
freshly loaded).

Selectors
─────────
All locators target IDs and data-testid attributes defined in
app/static/index.html.
"""

import json
import re

import pytest

pytestmark = pytest.mark.e2e
from playwright.sync_api import Page, expect


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def register_via_ui(page: Page, url: str = "https://example.com/test") -> str:
    """Fill the form, submit, wait for the new row, return its job_id."""
    page.fill("#job-url-input", url)
    page.click("#create-job-btn")
    page.wait_for_selector("#jobs-list tr")
    return page.locator("#jobs-list tr").last.get_attribute("data-job-id")


def api_post(page: Page, path: str, payload: dict | None = None) -> dict:
    """Send a JSON POST via Playwright's request context and return the body."""
    kwargs: dict = {"headers": {"Content-Type": "application/json"}}
    if payload is not None:
        kwargs["data"] = json.dumps(payload)
    return page.request.post(path, **kwargs).json()


def api_delete(page: Page, path: str) -> int:
    """Send a DELETE request and return the HTTP status code."""
    return page.request.delete(path).status


# ---------------------------------------------------------------------------
# Page load  (uses plain `page` — tests raw default state)
# ---------------------------------------------------------------------------

class TestPageLoad:
    def test_page_title(self, page: Page, live_server):
        page.goto(live_server)
        expect(page).to_have_title("Web Extraction Manager")

    def test_main_heading_visible(self, page: Page, live_server):
        page.goto(live_server)
        expect(page.locator("h1")).to_have_text("Web Extraction Manager")

    def test_operator_dropdown_has_five_options(self, page: Page, live_server):
        page.goto(live_server)
        expect(page.locator("#operator-select option")).to_have_count(5)

    def test_default_operator_is_alice(self, page: Page, live_server):
        page.goto(live_server)
        expect(page.locator("#operator-select")).to_have_value("alice")

    def test_credit_balance_loads_on_startup(self, page: Page, live_server):
        page.goto(live_server)
        expect(page.locator("#credit-balance")).not_to_have_text("—", timeout=3_000)

    def test_empty_state_shown_when_no_jobs(self, page: Page, live_server):
        """
        Navigate as a brand-new operator so the job list is guaranteed empty
        regardless of what other tests have done to alice.
        """
        import uuid
        fresh = f"op-{uuid.uuid4().hex[:8]}"
        page.goto(live_server)
        page.evaluate(f"currentOperator = '{fresh}'; loadAll();")
        page.wait_for_function(
            "document.getElementById('credit-balance').textContent !== '—'"
        )
        expect(page.locator("#no-jobs-message")).to_be_visible()
        expect(page.locator("#jobs-table")).to_be_hidden()


# ---------------------------------------------------------------------------
# Register job
# ---------------------------------------------------------------------------

class TestRegisterJob:
    def test_empty_url_shows_validation_error(self, isolated_page: Page):
        isolated_page.click("#create-job-btn")
        expect(isolated_page.locator("#create-job-message")).to_be_visible()
        expect(isolated_page.locator("#create-job-message")).to_contain_text("Please enter a URL")

    def test_empty_url_does_not_create_a_job(self, isolated_page: Page):
        isolated_page.click("#create-job-btn")
        expect(isolated_page.locator("#no-jobs-message")).to_be_visible()

    def test_register_shows_success_banner(self, isolated_page: Page):
        isolated_page.fill("#job-url-input", "https://example.com/test")
        isolated_page.click("#create-job-btn")
        expect(isolated_page.locator("#create-job-message")).to_contain_text("Job registered successfully")

    def test_url_input_cleared_after_register(self, isolated_page: Page):
        isolated_page.fill("#job-url-input", "https://example.com/test")
        isolated_page.click("#create-job-btn")
        isolated_page.wait_for_selector("#jobs-list tr")
        expect(isolated_page.locator("#job-url-input")).to_have_value("")

    def test_registered_job_appears_in_table(self, isolated_page: Page):
        isolated_page.fill("#job-url-input", "https://example.com/test")
        isolated_page.click("#create-job-btn")
        expect(isolated_page.locator("#jobs-table")).to_be_visible(timeout=3_000)
        expect(isolated_page.locator("#jobs-list tr")).to_have_count(1)

    def test_registered_job_shows_correct_url(self, isolated_page: Page):
        isolated_page.fill("#job-url-input", "https://example.com/my-page")
        isolated_page.click("#create-job-btn")
        isolated_page.wait_for_selector("#jobs-list tr")
        expect(isolated_page.locator("#jobs-list td a").first).to_have_text("https://example.com/my-page")

    def test_registered_job_has_pending_status(self, isolated_page: Page):
        isolated_page.fill("#job-url-input", "https://example.com/test")
        isolated_page.click("#create-job-btn")
        isolated_page.wait_for_selector("[data-testid^='job-status-']")
        expect(isolated_page.locator("[data-testid^='job-status-']").first).to_have_text("pending")

    def test_pending_job_start_enabled_stop_disabled(self, isolated_page: Page):
        isolated_page.fill("#job-url-input", "https://example.com/test")
        isolated_page.click("#create-job-btn")
        isolated_page.wait_for_selector("[data-testid^='btn-start-']")
        expect(isolated_page.locator("[data-testid^='btn-start-']").first).to_be_enabled()
        expect(isolated_page.locator("[data-testid^='btn-stop-']").first).to_be_disabled()

    def test_multiple_jobs_each_get_own_row(self, isolated_page: Page):
        isolated_page.fill("#job-url-input", "https://example.com/first")
        isolated_page.click("#create-job-btn")
        isolated_page.wait_for_selector("#jobs-list tr")
        isolated_page.fill("#job-url-input", "https://example.com/second")
        isolated_page.click("#create-job-btn")
        expect(isolated_page.locator("#jobs-list tr")).to_have_count(2, timeout=3_000)


# ---------------------------------------------------------------------------
# Start job
# ---------------------------------------------------------------------------

class TestStartJob:
    def test_start_job_reaches_completed_status(self, isolated_page: Page):
        register_via_ui(isolated_page)
        isolated_page.locator("[data-testid^='btn-start-']").first.click()
        expect(isolated_page.locator("[data-testid^='job-status-']").first).to_have_text(
            "completed", timeout=5_000
        )

    def test_start_job_decrements_credit_balance(self, isolated_page: Page):
        register_via_ui(isolated_page)
        isolated_page.locator("[data-testid^='btn-start-']").first.click()
        expect(isolated_page.locator("[data-testid^='job-status-']").first).to_have_text(
            "completed", timeout=5_000
        )
        # Unique operator always starts at 100 — exact assertion is safe.
        expect(isolated_page.locator("#credit-balance")).to_have_text("99")

    def test_start_job_increments_pages_processed(self, isolated_page: Page):
        register_via_ui(isolated_page)
        isolated_page.locator("[data-testid^='btn-start-']").first.click()
        expect(isolated_page.locator("[data-testid^='job-status-']").first).to_have_text(
            "completed", timeout=5_000
        )
        expect(isolated_page.locator("[data-testid^='job-pages-']").first).to_have_text("1")

    def test_completed_job_both_buttons_disabled(self, isolated_page: Page):
        register_via_ui(isolated_page)
        isolated_page.locator("[data-testid^='btn-start-']").first.click()
        expect(isolated_page.locator("[data-testid^='job-status-']").first).to_have_text(
            "completed", timeout=5_000
        )
        expect(isolated_page.locator("[data-testid^='btn-start-']").first).to_be_disabled()
        expect(isolated_page.locator("[data-testid^='btn-stop-']").first).to_be_disabled()


# ---------------------------------------------------------------------------
# Stop job
# ---------------------------------------------------------------------------

class TestStopJob:
    def test_running_job_has_stop_enabled_start_disabled(self, isolated_page: Page, operator):
        job_id = register_via_ui(isolated_page)

        isolated_page.route(
            re.compile(r".*/api/jobs\?.*"),
            lambda route: route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps([
                    {"id": job_id, "owner": operator,
                     "url": "https://example.com/test",
                     "status": "running", "pages_processed": 0}
                ]),
            ),
        )
        isolated_page.click("#refresh-jobs-btn")

        expect(isolated_page.locator(f"[data-testid='btn-stop-{job_id}']")).to_be_enabled(timeout=3_000)
        expect(isolated_page.locator(f"[data-testid='btn-start-{job_id}']")).to_be_disabled()

    def test_clicking_stop_sends_stop_request(self, isolated_page: Page, operator):
        job_id = register_via_ui(isolated_page)
        escaped = re.escape(job_id)

        isolated_page.route(
            re.compile(r".*/api/jobs\?.*"),
            lambda route: route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps([
                    {"id": job_id, "owner": operator,
                     "url": "https://example.com/test",
                     "status": "running", "pages_processed": 0}
                ]),
            ),
        )
        isolated_page.route(
            re.compile(rf".*/api/jobs/{escaped}/stop"),
            lambda route: route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {"id": job_id, "owner": operator,
                     "url": "https://example.com/test",
                     "status": "stopped", "pages_processed": 0}
                ),
            ),
        )

        isolated_page.click("#refresh-jobs-btn")
        expect(isolated_page.locator(f"[data-testid='btn-stop-{job_id}']")).to_be_enabled(timeout=3_000)

        with isolated_page.expect_response(re.compile(rf".*/api/jobs/{escaped}/stop")) as resp_info:
            isolated_page.locator(f"[data-testid='btn-stop-{job_id}']").click()

        resp = resp_info.value
        assert resp.status == 200
        assert resp.json()["status"] == "stopped"

    def test_stopped_job_shows_stopped_status_badge(self, isolated_page: Page, operator):
        data = api_post(isolated_page, "/api/jobs", {"user_id": operator, "url": "https://example.com/stop-badge"})
        job_id = data["id"]
        api_post(isolated_page, f"/api/jobs/{job_id}/start")
        api_post(isolated_page, f"/api/jobs/{job_id}/stop")

        isolated_page.click("#refresh-jobs-btn")
        expect(isolated_page.locator(f"[data-testid='job-status-{job_id}']")).to_have_text(
            "stopped", timeout=3_000
        )

    def test_stopped_job_both_buttons_disabled(self, isolated_page: Page, operator):
        data = api_post(isolated_page, "/api/jobs", {"user_id": operator, "url": "https://example.com/stop-disabled"})
        job_id = data["id"]
        api_post(isolated_page, f"/api/jobs/{job_id}/start")
        api_post(isolated_page, f"/api/jobs/{job_id}/stop")

        isolated_page.click("#refresh-jobs-btn")
        isolated_page.wait_for_selector(f"[data-testid='job-status-{job_id}']")
        expect(isolated_page.locator(f"[data-testid='btn-start-{job_id}']")).to_be_disabled()
        expect(isolated_page.locator(f"[data-testid='btn-stop-{job_id}']")).to_be_disabled()

    def test_stopped_job_pages_not_decremented_on_stop(self, isolated_page: Page, operator):
        data = api_post(isolated_page, "/api/jobs", {"user_id": operator, "url": "https://example.com/credits-no-refund"})
        job_id = data["id"]
        api_post(isolated_page, f"/api/jobs/{job_id}/start")
        api_post(isolated_page, f"/api/jobs/{job_id}/stop")

        isolated_page.click("#refresh-jobs-btn")
        isolated_page.wait_for_selector(f"[data-testid='job-status-{job_id}']")
        expect(isolated_page.locator(f"[data-testid='job-pages-{job_id}']")).to_have_text("0")


# ---------------------------------------------------------------------------
# Delete job
# ---------------------------------------------------------------------------

class TestDeleteJob:
    def test_delete_button_present_on_every_row(self, isolated_page: Page):
        register_via_ui(isolated_page)
        isolated_page.wait_for_selector("[data-testid^='btn-delete-']")
        expect(isolated_page.locator("[data-testid^='btn-delete-']").first).to_be_visible()

    def test_clicking_delete_shows_inline_confirmation(self, isolated_page: Page):
        job_id = register_via_ui(isolated_page)
        isolated_page.locator(f"[data-testid='btn-delete-{job_id}']").click()
        expect(isolated_page.locator(f"[data-testid='btn-delete-confirm-{job_id}']")).to_be_visible()
        expect(isolated_page.locator(f"[data-testid='btn-delete-cancel-{job_id}']")).to_be_visible()

    def test_cancel_restores_original_buttons(self, isolated_page: Page):
        job_id = register_via_ui(isolated_page)
        isolated_page.locator(f"[data-testid='btn-delete-{job_id}']").click()
        isolated_page.locator(f"[data-testid='btn-delete-cancel-{job_id}']").click()
        expect(isolated_page.locator(f"[data-testid='btn-delete-{job_id}']")).to_be_visible(timeout=3_000)

    def test_confirm_removes_job_row(self, isolated_page: Page):
        job_id = register_via_ui(isolated_page)
        isolated_page.locator(f"[data-testid='btn-delete-{job_id}']").click()
        isolated_page.locator(f"[data-testid='btn-delete-confirm-{job_id}']").click()
        expect(isolated_page.locator(f"[data-job-id='{job_id}']")).to_have_count(0, timeout=3_000)

    def test_confirm_shows_empty_state_when_last_job_deleted(self, isolated_page: Page):
        job_id = register_via_ui(isolated_page)
        isolated_page.locator(f"[data-testid='btn-delete-{job_id}']").click()
        isolated_page.locator(f"[data-testid='btn-delete-confirm-{job_id}']").click()
        expect(isolated_page.locator("#no-jobs-message")).to_be_visible(timeout=3_000)

    def test_deleting_one_job_leaves_others_intact(self, isolated_page: Page):
        job_id_1 = register_via_ui(isolated_page, "https://example.com/keep")
        job_id_2 = register_via_ui(isolated_page, "https://example.com/delete-me")
        isolated_page.locator(f"[data-testid='btn-delete-{job_id_2}']").click()
        isolated_page.locator(f"[data-testid='btn-delete-confirm-{job_id_2}']").click()
        expect(isolated_page.locator(f"[data-job-id='{job_id_2}']")).to_have_count(0, timeout=3_000)
        expect(isolated_page.locator(f"[data-job-id='{job_id_1}']")).to_be_visible()


# ---------------------------------------------------------------------------
# Operator isolation
# ---------------------------------------------------------------------------

class TestOperatorIsolation:
    def test_switching_operator_shows_empty_list(self, isolated_page: Page, operator):
        """
        Register a job as the test operator, switch to a second fresh operator,
        verify the second operator sees no jobs.
        """
        import uuid
        second = f"op-{uuid.uuid4().hex[:8]}"
        register_via_ui(isolated_page)
        expect(isolated_page.locator("#jobs-list tr")).to_have_count(1)

        isolated_page.evaluate(f"currentOperator = '{second}'; loadAll();")
        expect(isolated_page.locator("#no-jobs-message")).to_be_visible(timeout=3_000)
        expect(isolated_page.locator("#jobs-table")).to_be_hidden()

    def test_switching_operator_updates_credit_display(self, isolated_page: Page, operator):
        """After operator A spends a credit, switching to fresh operator B still shows 100."""
        import uuid
        second = f"op-{uuid.uuid4().hex[:8]}"
        register_via_ui(isolated_page)
        isolated_page.locator("[data-testid^='btn-start-']").first.click()
        expect(isolated_page.locator("[data-testid^='job-status-']").first).to_have_text(
            "completed", timeout=5_000
        )
        expect(isolated_page.locator("#credit-balance")).to_have_text("99")

        isolated_page.evaluate(f"currentOperator = '{second}'; loadAll();")
        expect(isolated_page.locator("#credit-balance")).to_have_text("100", timeout=3_000)

    def test_switching_back_restores_previous_operator_jobs(self, isolated_page: Page, operator):
        import uuid
        second = f"op-{uuid.uuid4().hex[:8]}"
        register_via_ui(isolated_page)
        expect(isolated_page.locator("#jobs-list tr")).to_have_count(1)

        isolated_page.evaluate(f"currentOperator = '{second}'; loadAll();")
        expect(isolated_page.locator("#no-jobs-message")).to_be_visible(timeout=3_000)

        isolated_page.evaluate(f"currentOperator = '{operator}'; loadAll();")
        expect(isolated_page.locator("#jobs-list tr")).to_have_count(1, timeout=3_000)

    def test_each_operator_has_independent_credits(self, isolated_page: Page, operator):
        import uuid
        second = f"op-{uuid.uuid4().hex[:8]}"
        expect(isolated_page.locator("#credit-balance")).to_have_text("100")

        isolated_page.evaluate(f"currentOperator = '{second}'; loadAll();")
        expect(isolated_page.locator("#credit-balance")).to_have_text("100", timeout=3_000)

    def test_dropdown_switch_isolates_jobs(self, isolated_page: Page):
        """Verify the actual dropdown element triggers correct isolation."""
        register_via_ui(isolated_page)
        expect(isolated_page.locator("#jobs-list tr")).to_have_count(1)

        # Switch to a named operator via the real dropdown UI.
        # "carol" is a known dropdown option never used by other tests.
        isolated_page.select_option("#operator-select", "carol")
        expect(isolated_page.locator("#no-jobs-message")).to_be_visible(timeout=3_000)


# ---------------------------------------------------------------------------
# Refresh button
# ---------------------------------------------------------------------------

class TestRefreshButton:
    def test_refresh_picks_up_api_registered_job(self, isolated_page: Page, operator):
        api_post(isolated_page, "/api/jobs", {"user_id": operator, "url": "https://example.com/api-registered"})
        isolated_page.click("#refresh-jobs-btn")
        expect(isolated_page.locator("#jobs-list tr")).to_have_count(1, timeout=3_000)

    def test_refresh_shows_updated_status(self, isolated_page: Page, operator):
        data = api_post(isolated_page, "/api/jobs", {"user_id": operator, "url": "https://example.com/update-test"})
        job_id = data["id"]

        isolated_page.click("#refresh-jobs-btn")
        expect(isolated_page.locator(f"[data-testid='job-status-{job_id}']")).to_have_text("pending", timeout=3_000)

        api_post(isolated_page, f"/api/jobs/{job_id}/start")
        isolated_page.wait_for_timeout(300)  # let the 100 ms simulation finish

        isolated_page.click("#refresh-jobs-btn")
        expect(isolated_page.locator(f"[data-testid='job-status-{job_id}']")).to_have_text("completed", timeout=3_000)
