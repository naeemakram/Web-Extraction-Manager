import pytest
from unittest.mock import patch

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# GET /api/credits  — retrieve credit balance for a user
# ---------------------------------------------------------------------------

class TestGetCredits:
    def test_returns_200(self, client):
        with patch("app.api.credits.credit_service.get_credits", return_value=100):
            response = client.get("/api/credits?user_id=user1")
        assert response.status_code == 200

    def test_response_contains_credits_field(self, client):
        with patch("app.api.credits.credit_service.get_credits", return_value=100):
            response = client.get("/api/credits?user_id=user1")
        data = response.get_json()
        assert data["credits"] == 100

    def test_response_contains_user_id_field(self, client):
        with patch("app.api.credits.credit_service.get_credits", return_value=100):
            response = client.get("/api/credits?user_id=user1")
        data = response.get_json()
        assert data["user_id"] == "user1"

    def test_calls_service_with_user_id(self, client):
        with patch("app.api.credits.credit_service.get_credits") as mock:
            mock.return_value = 100
            client.get("/api/credits?user_id=user1")
        mock.assert_called_once_with("user1")

    def test_reflects_reduced_balance(self, client):
        with patch("app.api.credits.credit_service.get_credits", return_value=57):
            response = client.get("/api/credits?user_id=user1")
        assert response.get_json()["credits"] == 57

    def test_reflects_zero_balance(self, client):
        with patch("app.api.credits.credit_service.get_credits", return_value=0):
            response = client.get("/api/credits?user_id=user1")
        assert response.get_json()["credits"] == 0

    def test_missing_user_id_returns_400(self, client):
        response = client.get("/api/credits")
        assert response.status_code == 400
