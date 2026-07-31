import time
from typing import Any, Optional

import requests

from app import config

BASE_URL = "https://api.adzuna.com/v1/api/jobs/in"


class AdzunaConfigError(Exception):
    pass


class AdzunaAPIError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


_cache: dict[tuple, tuple[float, Any]] = {}


def _cached_get(url: str, params: dict[str, Any]) -> dict[str, Any]:
    key = (url, tuple(sorted(params.items())))
    now = time.time()
    cached = _cache.get(key)
    if cached and now - cached[0] < config.ADZUNA_CACHE_TTL_SECONDS:
        return cached[1]

    if not config.ADZUNA_APP_ID or not config.ADZUNA_APP_KEY:
        raise AdzunaConfigError(
            "Adzuna API keys not configured — set ADZUNA_APP_ID and ADZUNA_APP_KEY in .env "
            "(see USER_MANUAL.md)."
        )

    request_params = {
        "app_id": config.ADZUNA_APP_ID,
        "app_key": config.ADZUNA_APP_KEY,
        "content-type": "application/json",
        **params,
    }

    try:
        resp = requests.get(url, params=request_params, timeout=10)
    except requests.exceptions.RequestException as exc:
        raise AdzunaAPIError(f"Could not reach Adzuna: {exc}") from exc

    if resp.status_code in (401, 403):
        raise AdzunaAPIError("Adzuna rejected the request — check your API keys.", resp.status_code)
    if resp.status_code == 429:
        raise AdzunaAPIError("Adzuna rate limit hit — try again shortly.", resp.status_code)
    if resp.status_code >= 400:
        raise AdzunaAPIError(f"Adzuna returned an error (HTTP {resp.status_code}).", resp.status_code)

    data = resp.json()
    _cache[key] = (now, data)
    return data


def search_jobs(
    what: str = "",
    where: str = "",
    page: int = 1,
    results_per_page: int = 20,
    category: Optional[str] = None,
) -> list[dict[str, Any]]:
    page = max(page, 1)
    results_per_page = min(max(results_per_page, 1), 50)
    url = f"{BASE_URL}/search/{page}"
    params: dict[str, Any] = {"results_per_page": results_per_page}
    if what:
        params["what"] = what
    if where:
        params["where"] = where
    if category:
        params["category"] = category

    data = _cached_get(url, params)
    results = []
    for item in data.get("results", []):
        results.append({
            "source": "adzuna",
            "external_id": str(item.get("id")) if item.get("id") else None,
            "title": item.get("title") or "",
            "company": (item.get("company") or {}).get("display_name"),
            "location": (item.get("location") or {}).get("display_name"),
            "description": item.get("description"),
            "url": item.get("redirect_url"),
            "salary_min": item.get("salary_min"),
            "salary_max": item.get("salary_max"),
            "category": (item.get("category") or {}).get("label"),
            "posted_at": item.get("created"),
        })
    return results


def get_salary_histogram(what: str = "", where: str = "", category: Optional[str] = None) -> dict[str, Any]:
    url = f"{BASE_URL}/histogram"
    params: dict[str, Any] = {}
    if what:
        params["what"] = what
    if where:
        params["where"] = where
    if category:
        params["category"] = category
    return _cached_get(url, params)


def get_salary_history(what: str = "", where: str = "", months: int = 6) -> dict[str, Any]:
    url = f"{BASE_URL}/history"
    params: dict[str, Any] = {"months": months}
    if what:
        params["what"] = what
    if where:
        params["where"] = where
    return _cached_get(url, params)
