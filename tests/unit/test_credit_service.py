import pytest
from unittest.mock import patch

pytestmark = pytest.mark.unit
from app.services import credit_service, job_service
from app.models import store
from app import config


class TestGetCredits:
    def test_new_user_gets_default_credits(self):
        assert credit_service.get_credits("user1") == config.DEFAULT_CREDITS

    def test_existing_user_returns_current_balance(self):
        store.credits["user1"] = 42
        assert credit_service.get_credits("user1") == 42

    def test_credits_not_zero(self):
        assert credit_service.get_credits("t3st_us3r") > 0


class TestHasCredits:
    def test_has_credits_true_when_positive(self):
        store.credits["user1"] = 50
        assert credit_service.has_credits("user1") is True

    def test_has_credits_false_at_zero(self):
        store.credits["user1"] = 0
        assert credit_service.has_credits("user1") is False

    def test_new_user_has_credits(self):
        # A brand-new user is initialised with DEFAULT_CREDITS, so has_credits must be True.
        assert credit_service.has_credits("new_user") is True


class TestDeductCredit:
    def test_deduct_reduces_balance_by_one(self):
        store.credits["user1"] = 10
        credit_service.deduct_credit("user1")
        assert store.credits["user1"] == 9

    def test_deduct_returns_new_balance(self):
        store.credits["user1"] = 10
        new_balance = credit_service.deduct_credit("user1")
        assert new_balance == 9

    def test_deduct_multiple_times(self):
        store.credits["user1"] = 10
        credit_service.deduct_credit("user1")
        credit_service.deduct_credit("user1")
        credit_service.deduct_credit("user1")
        assert store.credits["user1"] == 7

    def test_deduct_does_not_go_below_zero(self):
        store.credits["user1"] = 0
        credit_service.deduct_credit("user1")
        assert store.credits["user1"] == 0

    def test_deduct_from_one_reaches_zero_not_negative(self):
        store.credits["user1"] = 1
        credit_service.deduct_credit("user1")
        assert store.credits["user1"] == 0


class TestCreditsNotRestoredOnStop:
    def test_credits_unchanged_after_stop(self):
        """Stopping a job must never refund credits."""
        job = job_service.register_job("user1", "https://example.com")
        with patch("time.sleep"):
            job_service.start_job(job.id)
        store.credits["user1"] = 97
        job_service.stop_job(job.id)
        assert credit_service.get_credits("user1") == 97
