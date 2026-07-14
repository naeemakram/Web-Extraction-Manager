from flask import Blueprint, request, jsonify
from app.services import credit_service

credits_bp = Blueprint("credits", __name__)


@credits_bp.get("/api/credits")
def get_credits():
    """
    Get the current credit balance for an operator.
    ---
    tags:
      - Credits
    parameters:
      - in: query
        name: user_id
        type: string
        required: true
        description: Operator user ID
        example: alice
    responses:
      200:
        description: Current credit balance for the operator
        schema:
          type: object
          properties:
            user_id:
              type: string
              description: The operator user ID echoed back
              example: alice
            credits:
              type: integer
              description: Remaining credit balance (new operators start at 100)
              example: 97
      400:
        description: user_id query parameter is missing
        schema:
          $ref: '#/definitions/Error'
    """
    user_id = request.args.get("user_id")
    if not user_id:
        return jsonify({"error": "user_id is required"}), 400
    credits = credit_service.get_credits(user_id)
    return jsonify({"user_id": user_id, "credits": credits}), 200
