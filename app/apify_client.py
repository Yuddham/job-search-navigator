"""Apify client -- runs specific job-search Actors (hosted scrapers on Apify's
own infrastructure/proxies, not this machine) and normalizes each one's
dataset output into this app's common listing shape.

Scope note: this project's root CLAUDE.md previously declined automated
job-site scraping twice. This module is a deliberate, later reversal of that
stance for public job-LISTING data specifically, requested and confirmed by
the project owner -- it still never touches personal/contact data (see
apollo_client.py for that boundary), and every request runs through Apify's
own proxy infrastructure rather than this app directly hitting these sites.
Keep it scoped to public job listings only.

Four Actors, one per source, each called via Apify's run-sync-get-dataset-items
endpoint (one HTTP call runs the Actor to completion and returns its results --
no separate polling loop needed):
  - Google Jobs search   (gio21/google-jobs-scraper)
  - Naukri.com           (muhammetakkurtt/naukri-job-scraper)
  - Indeed India         (kaix/indeed-scraper)
  - LinkedIn Jobs search (curious_coder/linkedin-jobs-scraper)
"""
import json
import time
from typing import Any, Optional
from urllib.parse import urlencode

import requests

from app import config

BASE_URL = "https://api.apify.com/v2"

GOOGLE_JOBS_ACTOR = "gio21/google-jobs-scraper"
NAUKRI_ACTOR = "muhammetakkurtt/naukri-job-scraper"
INDEED_ACTOR = "kaix/indeed-scraper"
LINKEDIN_JOBS_ACTOR = "curious_coder/linkedin-jobs-scraper"

NAUKRI_MIN_JOBS = 50  # the Actor itself rejects maxJobs below this


class ApifyConfigError(Exception):
    pass


class ApifyAPIError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


_cache: dict[str, tuple[float, Any]] = {}


def clear_cache() -> None:
    _cache.clear()


def validate_token() -> dict[str, Any]:
    """Checks APIFY_API_TOKEN against Apify's own identity endpoint
    (GET /users/me) -- this only confirms the token, it never runs an Actor
    and isn't billed, unlike search_* below."""
    if not config.APIFY_API_TOKEN:
        raise ApifyConfigError(
            "Apify API token not configured -- set APIFY_API_TOKEN in .env (see USER_MANUAL.md)."
        )

    try:
        resp = requests.get(f"{BASE_URL}/users/me", params={"token": config.APIFY_API_TOKEN}, timeout=10)
    except requests.exceptions.RequestException as exc:
        raise ApifyAPIError(f"Could not reach Apify: {exc}") from exc

    if resp.status_code in (401, 403):
        raise ApifyAPIError("Apify rejected the token -- check APIFY_API_TOKEN.", resp.status_code)
    if resp.status_code >= 400:
        raise ApifyAPIError(f"Apify returned an error (HTTP {resp.status_code}).", resp.status_code)

    try:
        return resp.json()
    except ValueError as exc:
        raise ApifyAPIError("Apify returned an unreadable response.") from exc


def _get_path(d: dict, path: str, default: Any = None) -> Any:
    cur: Any = d
    for part in path.split("."):
        if not isinstance(cur, dict):
            return default
        cur = cur.get(part)
    return cur if cur is not None else default


def _run_actor_sync(actor: str, run_input: dict[str, Any]) -> list[dict]:
    """Runs an Actor to completion and returns its dataset items in one call."""
    key = json.dumps([actor, run_input], sort_keys=True, default=str)
    now = time.time()
    cached = _cache.get(key)
    if cached and now - cached[0] < config.APIFY_CACHE_TTL_SECONDS:
        return cached[1]

    if not config.APIFY_API_TOKEN:
        raise ApifyConfigError(
            "Apify API token not configured -- set APIFY_API_TOKEN in .env (see USER_MANUAL.md)."
        )

    actor_path = actor.replace("/", "~")
    url = f"{BASE_URL}/acts/{actor_path}/run-sync-get-dataset-items"
    params = {"token": config.APIFY_API_TOKEN, "timeout": config.APIFY_RUN_TIMEOUT_SECONDS}

    try:
        resp = requests.post(
            url, params=params, json=run_input, timeout=config.APIFY_RUN_TIMEOUT_SECONDS + 15,
        )
    except requests.exceptions.RequestException as exc:
        raise ApifyAPIError(f"Could not reach Apify ({actor}): {exc}") from exc

    if resp.status_code in (401, 403):
        raise ApifyAPIError(f"Apify rejected the request for {actor} -- check APIFY_API_TOKEN.", resp.status_code)
    if resp.status_code == 429:
        raise ApifyAPIError(f"Apify rate limit hit for {actor} -- try again shortly.", resp.status_code)
    if resp.status_code >= 400:
        raise ApifyAPIError(f"Apify returned an error for {actor} (HTTP {resp.status_code}).", resp.status_code)

    try:
        items = resp.json()
    except ValueError as exc:
        raise ApifyAPIError(f"Apify returned an unreadable response for {actor}.") from exc

    if not isinstance(items, list):
        items = []

    _cache[key] = (now, items)
    return items


def search_google_jobs(keyword: str, location: str = "", max_items: Optional[int] = None) -> list[dict]:
    run_input: dict[str, Any] = {
        "queries": [keyword] if keyword else ["jobs"],
        "location": location,
        "countryCode": "in",
        "languageCode": "en",
        "maxItems": max_items or config.APIFY_MAX_ITEMS_PER_SOURCE,
        "datePosted": "week",
        "proxyConfiguration": {"useApifyProxy": True, "apifyProxyGroups": ["RESIDENTIAL"]},
    }
    items = _run_actor_sync(GOOGLE_JOBS_ACTOR, run_input)

    results = []
    for it in items:
        if not isinstance(it, dict) or not it.get("title"):
            continue
        apply_opts = it.get("applyOptions") or []
        results.append({
            "source": "google_jobs",
            "external_id": it.get("jobId"),
            "title": it.get("title") or "",
            "company": it.get("companyName"),
            "location": it.get("location"),
            "description": it.get("description"),
            "url": it.get("url") or (apply_opts[0].get("url") if apply_opts else None),
            "salary_min": it.get("salaryMin"),
            "salary_max": it.get("salaryMax"),
            "category": None,
            "posted_at": it.get("postedAtIso") or it.get("postedAt"),
        })
    return results


def _naukri_slug(text: str) -> str:
    return "-".join(text.strip().lower().split()) or "jobs"


def search_naukri(keyword: str, location: str = "", max_jobs: Optional[int] = None) -> list[dict]:
    run_input: dict[str, Any] = {
        "maxJobs": max(max_jobs or config.APIFY_MAX_ITEMS_PER_SOURCE, NAUKRI_MIN_JOBS),
    }
    if location:
        # This Actor's "cities" filter takes opaque Naukri-internal IDs, not city
        # names, so a search URL (Naukri's own public "<kw>-jobs-in-<city>" pattern)
        # is the only reliable way to pass a location without a lookup table.
        run_input["searchUrl"] = f"https://www.naukri.com/{_naukri_slug(keyword or 'jobs')}-jobs-in-{_naukri_slug(location)}"
    else:
        run_input["keyword"] = keyword or "jobs"

    items = _run_actor_sync(NAUKRI_ACTOR, run_input)

    results = []
    for it in items:
        if not isinstance(it, dict) or not it.get("title"):
            continue
        salary_detail = it.get("salaryDetail") or {}
        results.append({
            "source": "naukri",
            "external_id": str(it.get("jobId")) if it.get("jobId") else None,
            "title": it.get("title") or "",
            "company": it.get("companyName"),
            "location": it.get("location"),
            "description": it.get("jobDescription"),
            "url": it.get("jdURL"),
            "salary_min": salary_detail.get("minimumSalary") or None,
            "salary_max": salary_detail.get("maximumSalary") or None,
            "category": None,
            "posted_at": it.get("createdDate"),
        })
    return results


def search_indeed(keyword: str, location: str = "", max_items: Optional[int] = None) -> list[dict]:
    run_input = {
        "keyword": keyword or "",
        "location": location or "India",
        "country": "IN",
        "maxItems": max_items or config.APIFY_MAX_ITEMS_PER_SOURCE,
        "searchMode": "basic",
        "proxyConfig": {"useApifyProxy": True},
    }
    items = _run_actor_sync(INDEED_ACTOR, run_input)

    results = []
    for it in items:
        if not isinstance(it, dict):
            continue
        title = _get_path(it, "title.text") or it.get("title")
        if not title:
            continue
        salary = it.get("salary") or {}
        results.append({
            "source": "indeed_in",
            "external_id": it.get("id"),
            "title": title,
            "company": _get_path(it, "company.name"),
            "location": _get_path(it, "location.formatted"),
            "description": _get_path(it, "description.text"),
            "url": _get_path(it, "urls.indeed") or _get_path(it, "apply.url"),
            "salary_min": salary.get("min"),
            "salary_max": salary.get("max"),
            "category": None,
            "posted_at": _get_path(it, "dates.posted"),
        })
    return results


def search_linkedin_jobs(keyword: str, location: str = "", count: Optional[int] = None) -> list[dict]:
    query: dict[str, str] = {}
    if keyword:
        query["keywords"] = keyword
    if location:
        query["location"] = location
    search_url = "https://www.linkedin.com/jobs/search/" + (f"?{urlencode(query)}" if query else "")

    run_input = {
        "urls": [search_url],
        "scrapeCompany": False,  # listing data only -- skip the extra per-job company scrape
        "count": count or config.APIFY_MAX_ITEMS_PER_SOURCE,
    }
    items = _run_actor_sync(LINKEDIN_JOBS_ACTOR, run_input)

    results = []
    for it in items:
        if not isinstance(it, dict) or it.get("error") or not it.get("title"):
            continue
        results.append({
            "source": "linkedin_jobs",
            "external_id": it.get("id"),
            "title": it.get("title") or "",
            "company": it.get("companyName"),
            "location": it.get("location"),
            "description": it.get("descriptionText"),
            "url": it.get("link"),
            "salary_min": None,
            "salary_max": None,
            "category": it.get("industries"),
            "posted_at": it.get("postedAt"),
        })
    return results
