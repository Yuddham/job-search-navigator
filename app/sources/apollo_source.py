import sqlite3

from app import apollo_client

NAME = "apollo"

MAX_COMPANIES_PER_SEARCH = 5


def fetch(conn: sqlite3.Connection, criteria: dict) -> tuple[list[dict], list[str]]:
    """Runs alongside adzuna_source/manual_source in Job Search -- searches
    companies matching the criteria's industries/keywords, then lists each
    company's open job postings via Apollo. Company + job-posting data only;
    never touches Apollo's people/contact endpoints."""
    keyword = (criteria.get("industries") or criteria.get("keywords") or criteria.get("target_roles") or "").strip()
    location = (criteria.get("locations") or "").strip()

    if not keyword:
        return [], []

    try:
        companies = apollo_client.search_companies(keyword=keyword, location=location, per_page=MAX_COMPANIES_PER_SEARCH)
    except apollo_client.ApolloConfigError as exc:
        return [], [str(exc)]
    except apollo_client.ApolloAPIError as exc:
        return [], [f"Apollo company search failed: {exc}"]

    results = []
    warnings = []
    for company in companies:
        org_id = company.get("id")
        if not org_id:
            continue
        try:
            postings = apollo_client.get_job_postings(org_id)
        except apollo_client.ApolloAPIError as exc:
            warnings.append(f"Apollo job postings failed for {company.get('name') or org_id}: {exc}")
            continue

        for jp in postings:
            results.append({
                "source": "apollo",
                "external_id": f"{org_id}:{jp.get('title')}",
                "title": jp.get("title") or "",
                "company": company.get("name"),
                "location": jp.get("location") or company.get("location"),
                "description": None,
                "url": jp.get("url"),
                "salary_min": None,
                "salary_max": None,
                "category": company.get("industry"),
                "posted_at": jp.get("posted_at"),
            })

    return results, warnings
