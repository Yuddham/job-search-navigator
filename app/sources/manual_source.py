import sqlite3

NAME = "manual"


def fetch(conn: sqlite3.Connection, criteria: dict) -> tuple[list[dict], list[str]]:
    rows = conn.execute("SELECT * FROM manual_listings ORDER BY id DESC").fetchall()
    results = []
    for r in rows:
        results.append({
            "source": "manual",
            "external_id": str(r["id"]),
            "title": r["title"],
            "company": r["company"],
            "location": r["location"],
            "description": r["description"],
            "url": r["url"],
            "salary_min": None,
            "salary_max": None,
            "category": None,
            "posted_at": r["created_at"],
        })
    return results, []
