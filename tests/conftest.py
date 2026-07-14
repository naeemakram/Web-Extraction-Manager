import pytest
from app.models import store


@pytest.fixture(autouse=True)
def reset_store():
    """Wipe all in-memory state before every test so nothing leaks between cases."""
    store.reset()
