import uuid
import time
import threading
from urllib.parse import urlparse

from app.models import store
from app.models.job import Job
from app.services import credit_service
from app import config


class JobNotFoundError(Exception):
    pass


class UserJobLimitError(Exception):
    pass


class SystemJobLimitError(Exception):
    pass


class InsufficientCreditsError(Exception):
    pass


class InvalidUrlError(Exception):
    pass


def _is_valid_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def register_job(user_id: str, url: str) -> Job:
    if not _is_valid_url(url):
        raise InvalidUrlError(f"Invalid URL: '{url}'. Must be an absolute http or https URL.")
    job = Job(id=str(uuid.uuid4()), owner=user_id, url=url)
    store.jobs[job.id] = job
    return job


def list_jobs(user_id: str) -> list:
    return [j for j in store.jobs.values() if j.owner == user_id]


def start_job(job_id: str) -> Job:
    job = _get_or_raise(job_id)

    if job.status != "pending":
        raise ValueError(f"Cannot start job with status '{job.status}'")

    if not credit_service.has_credits(job.owner):
        raise InsufficientCreditsError("No credits remaining")

    running_for_user = sum(
        1 for j in store.jobs.values()
        if j.owner == job.owner and j.status == "running"
    )
    if running_for_user >= config.USER_MAX_JOBS:
        raise UserJobLimitError("User concurrent job limit reached")

    running_total = sum(1 for j in store.jobs.values() if j.status == "running")
    if running_total >= config.SYSTEM_MAX_JOBS:
        raise SystemJobLimitError("System concurrent job limit reached")

    job.status = "running"
    thread = threading.Thread(target=_simulate, args=(job,), daemon=True)
    job._thread = thread
    thread.start()
    return job


def stop_job(job_id: str) -> Job:
    job = _get_or_raise(job_id)
    if job.status != "running":
        raise ValueError(f"Cannot stop job with status '{job.status}'")
    job.status = "stopped"
    return job


def delete_job(job_id: str) -> None:
    job = _get_or_raise(job_id)
    if job.status == "running":
        job.status = "stopped"  # signal background thread to abort cleanly
    del store.jobs[job_id]


def _get_or_raise(job_id: str) -> Job:
    if job_id not in store.jobs:
        raise JobNotFoundError(f"Job '{job_id}' not found")
    return store.jobs[job_id]


def _simulate(job: Job) -> None:
    # threading.Event.wait is used instead of time.sleep so that
    # patch("time.sleep") in tests doesn't make this return instantly —
    # tests need to observe "running" status after start_job returns.
    threading.Event().wait(timeout=0.1)
    if job.status != "running":
        return  # Job was stopped or store was reset; abort without side effects.
    job.pages_processed += 1
    credit_service.deduct_credit(job.owner)
    job.status = "completed"
