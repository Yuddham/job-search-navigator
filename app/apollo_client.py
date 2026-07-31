"""Apollo.io client -- STRICTLY SCOPED to organization/company data.

Only two Apollo endpoints are called anywhere in this module:
  - organization/company search (find companies by keyword/industry/location)
  - organization job postings (list a company's open roles)

Nothing in this file calls or wraps Apollo's people search, contacts,
email finder/verifier, sequences, campaigns, or tasks endpoints -- this
project deliberately does not do contact/email harvesting (see
USER_MANUAL.md / root CLAUDE.md for why). Keep it that way: if you're
tempted to add a "find the recruiter's email" helper here, don't --
that request has already been declined for this project.
"""
import json
import time
from typing import Any, Optional

import requests

from app import config

BASE_URL = "https://api.apollo.io/api/v1"


class ApolloConfigError(Exception):
    pass


class ApolloAPIError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


_cache: dict[str, tuple[float, Any]] = {}


def _cached_request(method: str, path: str, params: Optional[dict] = None, json_body: Optional[dict] = None) -> dict:
    # json.dumps(..., sort_keys=True) handles list-valued filters (e.g.
    # organization_locations) that a plain tuple(dict.items()) can't hash.
    key = json.dumps([method, path, params or {}, json_body or {}], sort_keys=True, default=str)
    now = time.time()
    cached = _cache.get(key)
    if cached and now - cached[0] < config.APOLLO_CACHE_TTL_SECONDS:
        return cached[1]

    if not config.APOLLO_API_KEY:
        raise ApolloConfigError(
            "Apollo API key not configured -- set APOLLO_API_KEY in .env (see USER_MANUAL.md)."
        )

    headers = {"X-Api-Key": config.APOLLO_API_KEY, "Content-Type": "application/json", "Accept": "application/json"}
    try:
        resp = requests.request(
            method, f"{BASE_URL}{path}", headers=headers, params=params, json=json_body, timeout=10,
        )
    except requests.exceptions.RequestException as exc:
        raise ApolloAPIError(f"Could not reach Apollo: {exc}") from exc

    if resp.status_code in (401, 403):
        raise ApolloAPIError("Apollo rejected the request -- check your API key/plan.", resp.status_code)
    if resp.status_code == 429:
        raise ApolloAPIError("Apollo rate limit hit -- try again shortly.", resp.status_code)
    if resp.status_code >= 400:
        raise ApolloAPIError(f"Apollo returned an error (HTTP {resp.status_code}).", resp.status_code)

    try:
        data = resp.json()
    except ValueError as exc:
        raise ApolloAPIError("Apollo returned an unreadable response.") from exc

    _cache[key] = (now, data)
    return data


def search_companies(keyword: str = "", location: str = "", per_page: int = 10) -> list[dict[str, Any]]:
    """Organization/company search only. Never touches people/contact endpoints."""
    payload: dict[str, Any] = {"per_page": min(max(per_page, 1), 25)}
    if keyword:
        payload["q_organization_keyword_tags"] = [keyword]
    if location:
        payload["organization_locations"] = [location]

    data = _cached_request("POST", "/mixed_companies/search", json_body=payload)
    orgs = data.get("organizations") or data.get("accounts") or []

    results = []
    for org in orgs:
        if not isinstance(org, dict):
            continue
        results.append({
            "id": org.get("id"),
            "name": org.get("name"),
            "website_url": org.get("website_url"),
            "industry": org.get("industry"),
            "location": org.get("city") or org.get("country") or None,
            "linkedin_url": org.get("linkedin_url"),
            "employee_count": org.get("estimated_num_employees"),
        })
    return results


def get_job_postings(organization_id: str) -> list[dict[str, Any]]:
    """Organization job postings only. Never touches people/contact endpoints."""
    if not organization_id:
        return []
    data = _cached_request("GET", f"/organizations/{organization_id}/job_postings")
    postings = data.get("organization_job_postings") or data.get("job_postings") or []

    results = []
    for jp in postings:
        if not isinstance(jp, dict):
            continue
        results.append({
            "title": jp.get("title") or jp.get("name"),
            "url": jp.get("url"),
            "location": jp.get("location") or jp.get("city"),
            "posted_at": jp.get("posted_at") or jp.get("last_seen_at"),
        })
    return results
