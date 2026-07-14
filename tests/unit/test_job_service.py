import pytest
from unittest.mock import patch

pytestmark = pytest.mark.unit
from app.services import job_service, credit_service
from app.models import store
from app import config
from app.services.job_service import (
    JobNotFoundError,
    UserJobLimitError,
    SystemJobLimitError,
    InsufficientCreditsError,
    InvalidUrlError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _start_and_join(job_id):
    """Start a job with sleep mocked out, then wait for the simulation thread."""
    with patch("time.sleep"):
        job = job_service.start_job(job_id)
    job._thread.join(timeout=2)
    return job


# ---------------------------------------------------------------------------
# register_job
# ---------------------------------------------------------------------------

class TestRegisterJob:
    def test_returns_pending_job(self):
        job = job_service.register_job("user1", "https://example.com")
        assert job.status == "pending"
        assert job.owner == "user1"
        assert job.url == "https://example.com"

    def test_assigns_unique_ids(self):
        job1 = job_service.register_job("user1", "https://a.com")
        job2 = job_service.register_job("user1", "https://b.com")
        assert job1.id != job2.id

    def test_job_stored_in_store(self):
        job = job_service.register_job("user1", "https://example.com")
        assert job.id in store.jobs

    def test_pages_processed_starts_at_zero(self):
        job = job_service.register_job("user1", "https://example.com")
        assert job.pages_processed == 0

    # --- URL validation ---

    @pytest.mark.parametrize("url", [
        "notaurl",               # no scheme, no netloc
        "example.com",           # no scheme
        "ftp://example.com",     # disallowed scheme
        "javascript:alert(1)",   # disallowed scheme
        "//example.com",         # scheme-relative (no scheme)
        "/relative/path",        # path-only
        "https://",              # scheme present but no netloc
        "",                      # empty string
    ])
    def test_raises_invalid_url_error_for_bad_url(self, url):
        with pytest.raises(InvalidUrlError):
            job_service.register_job("user1", url)

    @pytest.mark.parametrize("url", [
        "https://example.com",
        "http://example.com",
        "https://example.com/some/path",
        "https://example.com:8080/path?query=1#fragment",
        "http://localhost:5000",
    ])
    def test_accepts_valid_http_and_https_urls(self, url):
        job = job_service.register_job("user1", url)
        assert job.url == url

    def test_invalid_url_is_not_stored(self):
        with pytest.raises(InvalidUrlError):
            job_service.register_job("user1", "notaurl")
        assert len(store.jobs) == 0


# ---------------------------------------------------------------------------
# list_jobs
# ---------------------------------------------------------------------------

class TestListJobs:
    def test_returns_jobs_for_user(self):
        job = job_service.register_job("user1", "https://example.com")
        result = job_service.list_jobs("user1")
        assert job in result

    def test_excludes_other_users_jobs(self):
        job_service.register_job("user1", "https://a.com")
        job2 = job_service.register_job("user2", "https://b.com")
        result = job_service.list_jobs("user1")
        assert job2 not in result

    def test_empty_for_unknown_user(self):
        assert job_service.list_jobs("ghost") == []


# ---------------------------------------------------------------------------
# start_job — immediate state
# ---------------------------------------------------------------------------

class TestStartJob:
    def test_transitions_to_running(self):
        job = job_service.register_job("user1", "https://example.com")
        with patch("time.sleep"):
            job_service.start_job(job.id)
        assert job.status == "running"

    def test_raises_if_job_not_found(self):
        with pytest.raises(JobNotFoundError):
            job_service.start_job("nonexistent-id")

    def test_raises_when_no_credits(self):
        store.credits["user1"] = 0
        job = job_service.register_job("user1", "https://example.com")
        with pytest.raises(InsufficientCreditsError):
            job_service.start_job(job.id)

    def test_raises_when_user_limit_reached(self, monkeypatch):
        monkeypatch.setattr(config, "USER_MAX_JOBS", 1)
        job1 = job_service.register_job("user1", "https://a.com")
        job2 = job_service.register_job("user1", "https://b.com")
        with patch("time.sleep"):
            job_service.start_job(job1.id)
        with pytest.raises(UserJobLimitError):
            with patch("time.sleep"):
                job_service.start_job(job2.id)

    def test_raises_when_system_limit_reached(self, monkeypatch):
        monkeypatch.setattr(config, "SYSTEM_MAX_JOBS", 1)
        job1 = job_service.register_job("user1", "https://a.com")
        job2 = job_service.register_job("user2", "https://b.com")
        with patch("time.sleep"):
            job_service.start_job(job1.id)
        with pytest.raises(SystemJobLimitError):
            with patch("time.sleep"):
                job_service.start_job(job2.id)

    def test_raises_when_already_running(self):
        job = job_service.register_job("user1", "https://example.com")
        with patch("time.sleep"):
            job_service.start_job(job.id)
        with pytest.raises(ValueError):
            with patch("time.sleep"):
                job_service.start_job(job.id)


# ---------------------------------------------------------------------------
# start_job — simulation (post-thread)
# ---------------------------------------------------------------------------

class TestSimulation:
    def test_completes_after_simulation(self):
        job = job_service.register_job("user1", "https://example.com")
        _start_and_join(job.id)
        assert job.status == "completed"

    def test_increments_pages_processed(self):
        job = job_service.register_job("user1", "https://example.com")
        _start_and_join(job.id)
        assert job.pages_processed == 1

    def test_deducts_one_credit_per_page(self):
        job = job_service.register_job("user1", "https://example.com")
        credits_before = credit_service.get_credits("user1")
        _start_and_join(job.id)
        assert credit_service.get_credits("user1") == credits_before - 1


# ---------------------------------------------------------------------------
# stop_job
# ---------------------------------------------------------------------------

class TestStopJob:
    def test_transitions_running_job_to_stopped(self):
        job = job_service.register_job("user1", "https://example.com")
        with patch("time.sleep"):
            job_service.start_job(job.id)
        job_service.stop_job(job.id)
        assert job.status == "stopped"

    def test_raises_when_stopping_pending_job(self):
        job = job_service.register_job("user1", "https://example.com")
        with pytest.raises(ValueError):
            job_service.stop_job(job.id)

    def test_raises_if_job_not_found(self):
        with pytest.raises(JobNotFoundError):
            job_service.stop_job("nonexistent-id")

    def test_stop_does_not_reverse_credits(self):
        job = job_service.register_job("user1", "https://example.com")
        with patch("time.sleep"):
            job_service.start_job(job.id)
        # Simulate credits already spent.
        store.credits["user1"] = 95
        job_service.stop_job(job.id)
        assert credit_service.get_credits("user1") == 95


# ---------------------------------------------------------------------------
# delete_job
# ---------------------------------------------------------------------------

class TestDeleteJob:
    def test_removes_job_from_store(self):
        job = job_service.register_job("user1", "https://example.com")
        job_service.delete_job(job.id)
        assert job.id not in store.jobs

    def test_raises_if_job_not_found(self):
        with pytest.raises(JobNotFoundError):
            job_service.delete_job("nonexistent-id")

    def test_can_delete_pending_job(self):
        job = job_service.register_job("user1", "https://example.com")
        assert job.status == "pending"
        job_service.delete_job(job.id)
        assert job.id not in store.jobs

    def test_can_delete_stopped_job(self):
        job = job_service.register_job("user1", "https://example.com")
        with patch("time.sleep"):
            job_service.start_job(job.id)
        job_service.stop_job(job.id)
        job_service.delete_job(job.id)
        assert job.id not in store.jobs

    def test_can_delete_completed_job(self):
        job = job_service.register_job("user1", "https://example.com")
        _start_and_join(job.id)
        assert job.status == "completed"
        job_service.delete_job(job.id)
        assert job.id not in store.jobs

    def test_deleting_running_job_stops_thread_and_removes_job(self):
        job = job_service.register_job("user1", "https://example.com")
        with patch("time.sleep"):
            job_service.start_job(job.id)
        assert job.status == "running"
        job_service.delete_job(job.id)
        assert job.id not in store.jobs
        assert job.status == "stopped"

    def test_delete_does_not_affect_other_jobs(self):
        job1 = job_service.register_job("user1", "https://a.com")
        job2 = job_service.register_job("user1", "https://b.com")
        job_service.delete_job(job1.id)
        assert job1.id not in store.jobs
        assert job2.id in store.jobs
