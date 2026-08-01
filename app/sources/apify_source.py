import sqlite3
from concurrent.futures import ThreadPoolExecutor

from app import apify_client

NAME = "apify"

_JOBS = (
    ("Google Jobs", apify_client.search_google_jobs),
    ("Naukri", apify_client.search_naukri),
    ("Indeed India", apify_client.search_indeed),
    ("LinkedIn Jobs", apify_client.search_linkedin_jobs),
)


def fetch(conn: sqlite3.Connection, criteria: dict) -> tuple[list[dict], list[str]]:
    """Runs alongside adzuna_source/apollo_source/manual_source in Job Search --
    pulls public job-listing data from Google Jobs, Naukri, Indeed India, and
    LinkedIn Jobs via Apify's hosted Actors. The four run concurrently (each is
    an independent call to Apify's API, routed through Apify's own proxies --
    not repeated direct traffic from this machine to these sites) and fail
    independently, same as the other sources."""
    keyword = " ".join(
        filter(None, [criteria.get("keywords", ""), criteria.get("target_roles", "")])
    ).strip()
    location = (criteria.get("locations") or "").strip()

    if not keyword:
        return [], []

    def run(label: str, search_fn) -> tuple[list[dict], str | None, str | None]:
        try:
            return search_fn(keyword, location), None, None
        except apify_client.ApifyConfigError as exc:
            return [], str(exc), None
        except apify_client.ApifyAPIError as exc:
            return [], None, f"{label} search failed: {exc}"

    results: list[dict] = []
    warnings: list[str] = []
    config_error: str | None = None

    with ThreadPoolExecutor(max_workers=len(_JOBS)) as pool:
        futures = [pool.submit(run, label, search_fn) for label, search_fn in _JOBS]
        for future in futures:
            listings, cfg_err, warning = future.result()
            results.extend(listings)
            if cfg_err:
                config_error = cfg_err
            if warning:
                warnings.append(warning)

    if config_error:
        return [], [config_error]

    return results, warnings
