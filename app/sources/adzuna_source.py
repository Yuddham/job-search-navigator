import sqlite3

from app import adzuna_client

NAME = "adzuna"


def fetch(conn: sqlite3.Connection, criteria: dict) -> tuple[list[dict], list[str]]:
    what = " ".join(
        filter(None, [criteria.get("keywords", ""), criteria.get("target_roles", "")])
    ).strip()
    where = (criteria.get("locations") or "").strip()

    try:
        results = adzuna_client.search_jobs(what=what, where=where, results_per_page=20)
        return results, []
    except adzuna_client.AdzunaConfigError as exc:
        return [], [str(exc)]
    except adzuna_client.AdzunaAPIError as exc:
        return [], [f"Adzuna search failed: {exc}"]
