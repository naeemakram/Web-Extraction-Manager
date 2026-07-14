from app.models import store
from app import config


def get_credits(user_id: str) -> int:
    if user_id not in store.credits:
        store.credits[user_id] = config.DEFAULT_CREDITS
    return store.credits[user_id]


def has_credits(user_id: str) -> bool:
    return get_credits(user_id) > 0


def deduct_credit(user_id: str) -> int:
    new_balance = max(0, get_credits(user_id) - 1)
    store.credits[user_id] = new_balance
    return new_balance
