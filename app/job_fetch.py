import json
import re
from typing import Any, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from app import config

LOGIN_WALL_MARKERS = ["/login", "/authwall", "/checkpoint", "signin", "sign-in"]
CHROME_CLASS_KEYWORDS = ["nav", "footer", "sidebar", "cookie", "advert", "banner", "menu"]


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html or "", "lxml")
    for tag in soup.find_all(["br", "li", "p"]):
        tag.insert_after("\n")
    text = soup.get_text()
    return re.sub(r"\n{2,}", "\n", text).strip()


def _extract_json_ld(soup: BeautifulSoup) -> Optional[dict[str, Any]]:
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue

        candidates = data if isinstance(data, list) else [data]
        for item in list(candidates):
            if not isinstance(item, dict):
                continue
            graph = item.get("@graph")
            if isinstance(graph, list):
                candidates.extend(graph)
                continue

            types = item.get("@type")
            types = types if isinstance(types, list) else [types]
            if "JobPosting" not in types:
                continue

            org = item.get("hiringOrganization") or {}
            location = item.get("jobLocation") or {}
            address = location.get("address") if isinstance(location, dict) else {}
            location_text = None
            if isinstance(address, dict):
                location_text = ", ".join(
                    filter(None, [address.get("addressLocality"), address.get("addressRegion")])
                ) or None

            return {
                "title": item.get("title"),
                "company": org.get("name") if isinstance(org, dict) else None,
                "location": location_text,
                "jd_text": _html_to_text(item.get("description") or ""),
            }
    return None


def _extract_heuristic_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    for tag in soup.find_all(True):
        classes = tag.get("class") or []
        attrs = (" ".join(classes) + " " + (tag.get("id") or "")).lower()
        if any(k in attrs for k in CHROME_CLASS_KEYWORDS):
            tag.decompose()

    best_text = ""
    for candidate in soup.find_all(["div", "section", "article", "main"]):
        text = candidate.get_text(separator="\n", strip=True)
        if len(text) > len(best_text):
            best_text = text
    if not best_text:
        best_text = soup.get_text(separator="\n", strip=True)
    return best_text


def fetch_job_posting(url: str) -> dict[str, Any]:
    """Exactly one HTTP GET to the given URL -- no retries, no cookie/session
    persistence, no site-specific scraping logic. This is meant to read the
    single page a user explicitly pasted, not to crawl."""
    result: dict[str, Any] = {
        "status": "error", "title": None, "company": None, "location": None,
        "jd_text": None, "warning": None,
    }

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        result["warning"] = "Only http/https URLs are supported."
        return result

    try:
        resp = requests.get(
            url,
            headers={"User-Agent": config.JOB_FETCH_USER_AGENT},
            timeout=config.JOB_FETCH_TIMEOUT_SECONDS,
            allow_redirects=True,
        )
    except requests.exceptions.RequestException as exc:
        result["warning"] = (
            f"Could not fetch this page ({exc}). Please paste the job description text instead."
        )
        return result

    final_url = (resp.url or url).lower()

    if resp.status_code != 200:
        result["status"] = "blocked" if resp.status_code in (401, 403, 429) else "error"
        result["warning"] = (
            f"The page returned HTTP {resp.status_code} -- it may be blocking automated requests. "
            "Please paste the job description text instead."
        )
        return result

    if any(marker in final_url for marker in LOGIN_WALL_MARKERS):
        result["status"] = "blocked"
        result["warning"] = "This page redirected to a login page. Please paste the job description text instead."
        return result

    soup = BeautifulSoup(resp.text, "lxml")
    structured = _extract_json_ld(soup)
    if structured:
        result.update(structured)
    else:
        result["jd_text"] = _extract_heuristic_text(soup)

    text_len = len((result.get("jd_text") or "").strip())
    if text_len < config.JOB_FETCH_MIN_TEXT_CHARS:
        result["status"] = "blocked"
        result["warning"] = (
            "Not enough text could be extracted from this page (it may require a login or render mostly "
            "via JavaScript). Please paste the job description text instead."
        )
        return result

    result["status"] = "ok"
    return result
