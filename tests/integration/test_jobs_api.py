import pytest
from unittest.mock import patch, MagicMock

pytestmark = pytest.mark.integration
from app.models.job import Job
from app.services.job_service import (
    JobNotFoundError,
    UserJobLimitError,
    SystemJobLimitError,
    InsufficientCreditsError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_job(**overrides):
    """Return a Job instance with sensible defaults, overridable per test."""
    defaults = dict(
        id="job-abc-123",
        owner="user1",
        url="https://example.com",
        status="pending",
        pages_processed=0,
    )
    defaults.update(overrides)
    return Job(**defaults)


# ---------------------------------------------------------------------------
# POST /api/jobs  — register a job
# ---------------------------------------------------------------------------

class TestCreateJob:
    def test_returns_201(self, client):
        with patch("app.api.jobs.job_service.register_job") as mock:
            mock.return_value = make_job()
            response = client.post(
                "/api/jobs",
                json={"user_id": "user1", "url": "https://example.com"},
            )
        assert response.status_code == 201

    def test_response_contains_job_fields(self, client):
        job = make_job()
        with patch("app.api.jobs.job_service.register_job", return_value=job):
            response = client.post(
                "/api/jobs",
                json={"user_id": "user1", "url": "https://example.com"},
            )
        data = response.get_json()
        assert data["id"] == job.id
        assert data["owner"] == "user1"
        assert data["url"] == "https://example.com"
        assert data["status"] == "pending"
        assert data["pages_processed"] == 0

    def test_calls_service_with_correct_args(self, client):
        with patch("app.api.jobs.job_service.register_job") as mock:
            mock.return_value = make_job()
            client.post(
                "/api/jobs",
                json={"user_id": "user1", "url": "https://example.com"},
            )
        mock.assert_called_once_with("user1", "https://example.com")

    def test_missing_url_returns_400(self, client):
        response = client.post("/api/jobs", json={"user_id": "user1"})
        assert response.status_code == 400

    def test_missing_user_id_returns_400(self, client):
        response = client.post("/api/jobs", json={"url": "https://example.com"})
        assert response.status_code == 400

    def test_empty_body_returns_400(self, client):
        response = client.post("/api/jobs", json={})
        assert response.status_code == 400

    @pytest.mark.parametrize("url", [
        "notaurl",
        "ftp://example.com",
        "//example.com",
        "https://",
        "/relative/path",
    ])
    def test_invalid_url_returns_400(self, client, url):
        response = client.post("/api/jobs", json={"user_id": "user1", "url": url})
        assert response.status_code == 400

    def test_invalid_url_response_contains_error_message(self, client):
        response = client.post("/api/jobs", json={"user_id": "user1", "url": "notaurl"})
        assert "error" in response.get_json()


# ---------------------------------------------------------------------------
# GET /api/jobs  — list jobs for a user
# ---------------------------------------------------------------------------

class TestListJobs:
    def test_returns_200(self, client):
        with patch("app.api.jobs.job_service.list_jobs", return_value=[]):
            response = client.get("/api/jobs?user_id=user1")
        assert response.status_code == 200

    def test_returns_list_of_jobs(self, client):
        jobs = [make_job(id="job-1"), make_job(id="job-2")]
        with patch("app.api.jobs.job_service.list_jobs", return_value=jobs):
            response = client.get("/api/jobs?user_id=user1")
        data = response.get_json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["id"] == "job-1"
        assert data[1]["id"] == "job-2"

    def test_calls_service_with_user_id(self, client):
        with patch("app.api.jobs.job_service.list_jobs") as mock:
            mock.return_value = []
            client.get("/api/jobs?user_id=user1")
        mock.assert_called_once_with("user1")

    def test_missing_user_id_returns_400(self, client):
        response = client.get("/api/jobs")
        assert response.status_code == 400

    def test_empty_list_when_no_jobs(self, client):
        with patch("app.api.jobs.job_service.list_jobs", return_value=[]):
            response = client.get("/api/jobs?user_id=user1")
        assert response.get_json() == []


# ---------------------------------------------------------------------------
# POST /api/jobs/<id>/start
# ---------------------------------------------------------------------------

class TestStartJob:
    def test_returns_200(self, client):
        running_job = make_job(status="running")
        with patch("app.api.jobs.job_service.start_job", return_value=running_job):
            response = client.post("/api/jobs/job-abc-123/start")
        assert response.status_code == 200

    def test_response_shows_running_status(self, client):
        running_job = make_job(status="running")
        with patch("app.api.jobs.job_service.start_job", return_value=running_job):
            response = client.post("/api/jobs/job-abc-123/start")
        assert response.get_json()["status"] == "running"

    def test_calls_service_with_job_id(self, client):
        with patch("app.api.jobs.job_service.start_job") as mock:
            mock.return_value = make_job(status="running")
            client.post("/api/jobs/job-abc-123/start")
        mock.assert_called_once_with("job-abc-123")

    def test_job_not_found_returns_404(self, client):
        with patch("app.api.jobs.job_service.start_job", side_effect=JobNotFoundError):
            response = client.post("/api/jobs/bad-id/start")
        assert response.status_code == 404

    def test_no_credits_returns_402(self, client):
        with patch("app.api.jobs.job_service.start_job", side_effect=InsufficientCreditsError):
            response = client.post("/api/jobs/job-abc-123/start")
        assert response.status_code == 402

    def test_user_limit_returns_409(self, client):
        with patch("app.api.jobs.job_service.start_job", side_effect=UserJobLimitError):
            response = client.post("/api/jobs/job-abc-123/start")
        assert response.status_code == 409

    def test_system_limit_returns_409(self, client):
        with patch("app.api.jobs.job_service.start_job", side_effect=SystemJobLimitError):
            response = client.post("/api/jobs/job-abc-123/start")
        assert response.status_code == 409

    def test_invalid_state_returns_409(self, client):
        with patch("app.api.jobs.job_service.start_job", side_effect=ValueError):
            response = client.post("/api/jobs/job-abc-123/start")
        assert response.status_code == 409


# ---------------------------------------------------------------------------
# POST /api/jobs/<id>/stop
# ---------------------------------------------------------------------------

class TestStopJob:
    def test_returns_200(self, client):
        stopped_job = make_job(status="stopped")
        with patch("app.api.jobs.job_service.stop_job", return_value=stopped_job):
            response = client.post("/api/jobs/job-abc-123/stop")
        assert response.status_code == 200

    def test_response_shows_stopped_status(self, client):
        stopped_job = make_job(status="stopped")
        with patch("app.api.jobs.job_service.stop_job", return_value=stopped_job):
            response = client.post("/api/jobs/job-abc-123/stop")
        assert response.get_json()["status"] == "stopped"

    def test_calls_service_with_job_id(self, client):
        with patch("app.api.jobs.job_service.stop_job") as mock:
            mock.return_value = make_job(status="stopped")
            client.post("/api/jobs/job-abc-123/stop")
        mock.assert_called_once_with("job-abc-123")

    def test_job_not_found_returns_404(self, client):
        with patch("app.api.jobs.job_service.stop_job", side_effect=JobNotFoundError):
            response = client.post("/api/jobs/bad-id/stop")
        assert response.status_code == 404

    def test_job_not_running_returns_409(self, client):
        with patch("app.api.jobs.job_service.stop_job", side_effect=ValueError):
            response = client.post("/api/jobs/job-abc-123/stop")
        assert response.status_code == 409


# ---------------------------------------------------------------------------
# DELETE /api/jobs/<id>
# ---------------------------------------------------------------------------

class TestDeleteJob:
    def test_returns_204(self, client):
        with patch("app.api.jobs.job_service.delete_job"):
            response = client.delete("/api/jobs/job-abc-123")
        assert response.status_code == 204

    def test_response_body_is_empty(self, client):
        with patch("app.api.jobs.job_service.delete_job"):
            response = client.delete("/api/jobs/job-abc-123")
        assert response.data == b""

    def test_calls_service_with_job_id(self, client):
        with patch("app.api.jobs.job_service.delete_job") as mock:
            client.delete("/api/jobs/job-abc-123")
        mock.assert_called_once_with("job-abc-123")

    def test_job_not_found_returns_404(self, client):
        with patch("app.api.jobs.job_service.delete_job", side_effect=JobNotFoundError):
            response = client.delete("/api/jobs/bad-id")
        assert response.status_code == 404

    def test_job_not_found_response_contains_error(self, client):
        with patch("app.api.jobs.job_service.delete_job", side_effect=JobNotFoundError("Job 'bad-id' not found")):
            response = client.delete("/api/jobs/bad-id")
        assert "error" in response.get_json()
