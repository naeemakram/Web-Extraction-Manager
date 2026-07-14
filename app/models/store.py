jobs: dict = {}     # job_id → Job
credits: dict = {}  # user_id → int balance


def reset() -> None:
    # Mark any running jobs as stopped so their background threads abort cleanly
    # instead of writing to the freshly-cleared store after reset.
    for job in jobs.values():
        if job.status == "running":
            job.status = "stopped"
    jobs.clear()
    credits.clear()
