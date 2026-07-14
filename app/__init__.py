from flask import Flask, jsonify, send_from_directory
from flasgger import Swagger
from app.api.jobs import jobs_bp
from app.api.credits import credits_bp

_SWAGGER_TEMPLATE = {
    "swagger": "2.0",
    "info": {
        "title": "Web Extraction Manager API",
        "description": (
            "REST API for registering, managing, and monitoring web extraction jobs. "
            "Each operator draws from a monthly page-credit allowance. "
            "All state is held in memory — no persistence across server restarts."
        ),
        "version": "1.0.0",
        "contact": {"name": "Web Extraction Manager"},
    },
    "basePath": "/",
    "consumes": ["application/json"],
    "produces": ["application/json"],
    "tags": [
        {"name": "Jobs", "description": "Register, list, start, stop, and delete extraction jobs"},
        {"name": "Credits", "description": "Query the credit balance for an operator"},
    ],
    "definitions": {
        "Job": {
            "type": "object",
            "properties": {
                "id": {
                    "type": "string",
                    "description": "UUID assigned at registration",
                    "example": "550e8400-e29b-41d4-a716-446655440000",
                },
                "owner": {
                    "type": "string",
                    "description": "Operator user ID",
                    "example": "alice",
                },
                "url": {
                    "type": "string",
                    "description": "Absolute http/https URL to extract",
                    "example": "https://example.com/page",
                },
                "status": {
                    "type": "string",
                    "enum": ["pending", "running", "stopped", "completed"],
                    "description": "Current lifecycle state of the job",
                    "example": "pending",
                },
                "pages_processed": {
                    "type": "integer",
                    "description": "Number of pages processed so far (incremented by the simulation)",
                    "example": 0,
                },
            },
        },
        "Error": {
            "type": "object",
            "properties": {
                "error": {
                    "type": "string",
                    "description": "Human-readable error message",
                    "example": "user_id and url are required",
                }
            },
        },
    },
}

_SWAGGER_CONFIG = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/apispec.json",
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/apidocs/",
}


def create_app():
    app = Flask(__name__)
    app.register_blueprint(jobs_bp)
    app.register_blueprint(credits_bp)

    Swagger(app, template=_SWAGGER_TEMPLATE, config=_SWAGGER_CONFIG)

    @app.route("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    return app
