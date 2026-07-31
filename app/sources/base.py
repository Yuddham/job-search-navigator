import sqlite3
from typing import Protocol


class JobSource(Protocol):
    """Every source normalizes to the same listing shape and catches its own
    errors, so one source failing (e.g. Adzuna misconfigured) never blocks
    the others from showing results."""

    def fetch(self, conn: sqlite3.Connection, criteria: dict) -> tuple[list[dict], list[str]]:
        ...
