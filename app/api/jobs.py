from flask import Blueprint, request, jsonify
from app.services import job_service
from app.services.job_service import (
    JobNotFoundError,
    UserJobLimitError,
    SystemJobLimitError,
    InsufficientCreditsError,
    InvalidUrlError,
)

jobs_bp = Blueprint("jobs", __name__)


def _serialize(job):
    return {
        "id": job.id,
        "owner": job.owner,
        "url": job.url,
        "status": job.status,
        "pages_processed": job.pages_processed,
    }


@jobs_bp.post("/api/jobs")
def create_job():
    """
    Register a new extraction job.
    ---
    tags:
      - Jobs
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - user_id
            - url
          properties:
            user_id:
              type: string
              description: Operator user ID
              example: alice
            url:
              type: string
              description: Absolute http or https URL to extract
              example: https://example.com/page
    responses:
      201:
        description: Job registered successfully
        schema:
          $ref: '#/definitions/Job'
      400:
        description: Missing or invalid field (e.g. malformed URL, missing user_id)
        schema:
          $ref: '#/definitions/Error'
    """
    body = request.get_json(silent=True) or {}
    user_id = body.get("user_id")
    url = body.get("url")
    if not user_id or not url:
        return jsonify({"error": "user_id and url are required"}), 400
    try:
        job = job_service.register_job(user_id, url)
    except InvalidUrlError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(_serialize(job)), 201


@jobs_bp.get("/api/jobs")
def list_jobs():
    """
    List all jobs belonging to an operator.
    ---
    tags:
      - Jobs
    parameters:
      - in: query
        name: user_id
        type: string
        required: true
        description: Operator user ID
        example: alice
    responses:
      200:
        description: Array of jobs owned by the operator (may be empty)
        schema:
          type: array
          items:
            $ref: '#/definitions/Job'
      400:
        description: user_id query parameter is missing
        schema:
          $ref: '#/definitions/Error'
    """
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400
    jobs = job_service.list_jobs(user_id)
    return jsonify([_serialize(j) for j in jobs]), 200


@jobs_bp.post("/api/jobs/<job_id>/start")
def start_job(job_id):
    """
    Start a pending job.
    ---
    tags:
      - Jobs
    parameters:
      - in: path
        name: job_id
        type: string
        required: true
        description: UUID of the job to start
        example: 550e8400-e29b-41d4-a716-446655440000
    responses:
      200:
        description: Job started — status is now 'running'
        schema:
          $ref: '#/definitions/Job'
      402:
        description: Operator has no credits remaining
        schema:
          $ref: '#/definitions/Error'
      404:
        description: Job not found
        schema:
          $ref: '#/definitions/Error'
      409:
        description: >
          Job cannot be started — one of: job is not in pending state,
          operator has reached USER_MAX_JOBS concurrent jobs,
          or system has reached SYSTEM_MAX_JOBS concurrent jobs
        schema:
          $ref: '#/definitions/Error'
    """
    try:
        job = job_service.start_job(job_id)
        return jsonify(_serialize(job)), 200
    except JobNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except InsufficientCreditsError as e:
        return jsonify({"error": str(e)}), 402
    except (UserJobLimitError, SystemJobLimitError, ValueError) as e:
        return jsonify({"error": str(e)}), 409


@jobs_bp.post("/api/jobs/<job_id>/stop")
def stop_job(job_id):
    """
    Stop a running job.
    ---
    tags:
      - Jobs
    parameters:
      - in: path
        name: job_id
        type: string
        required: true
        description: UUID of the job to stop
        example: 550e8400-e29b-41d4-a716-446655440000
    responses:
      200:
        description: Job stopped — status is now 'stopped'. Credits already consumed are not refunded.
        schema:
          $ref: '#/definitions/Job'
      404:
        description: Job not found
        schema:
          $ref: '#/definitions/Error'
      409:
        description: Job is not currently running
        schema:
          $ref: '#/definitions/Error'
    """
    try:
        job = job_service.stop_job(job_id)
        return jsonify(_serialize(job)), 200
    except JobNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 409


@jobs_bp.delete("/api/jobs/<job_id>")
def delete_job(job_id):
    """
    Delete a job permanently.
    ---
    tags:
      - Jobs
    parameters:
      - in: path
        name: job_id
        type: string
        required: true
        description: UUID of the job to delete
        example: 550e8400-e29b-41d4-a716-446655440000
    responses:
      204:
        description: Job deleted. If the job was running, it is stopped before deletion. No body is returned.
      404:
        description: Job not found
        schema:
          $ref: '#/definitions/Error'
    """
    try:
        job_service.delete_job(job_id)
        return "", 204
    except JobNotFoundError as e:
        return jsonify({"error": str(e)}), 404
