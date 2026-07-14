from dataclasses import dataclass


@dataclass
class Job:
    id: str
    owner: str
    url: str
    status: str = "pending"
    pages_processed: int = 0

    def __post_init__(self):
        self._thread = None
