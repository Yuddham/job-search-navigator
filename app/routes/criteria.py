from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app import db
from app.models import SearchCriteriaIn, SearchCriteriaOut

router = APIRouter(prefix="/api/criteria", tags=["criteria"])


@router.get("", response_model=list[SearchCriteriaOut])
def list_criteria() -> list[SearchCriteriaOut]:
    with db.get_db() as conn:
        rows = conn.execute("SELECT * FROM search_criteria ORDER BY updated_at DESC").fetchall()
        return [SearchCriteriaOut(**dict(r)) for r in rows]


@router.post("", response_model=SearchCriteriaOut)
def create_criteria(payload: SearchCriteriaIn) -> SearchCriteriaOut:
    now = datetime.now(timezone.utc).isoformat()
    with db.get_db() as conn:
        cur = conn.execute(
            "INSERT INTO search_criteria (label, keywords, target_roles, industries, locations, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (payload.label, payload.keywords, payload.target_roles, payload.industries,
             payload.locations, now, now),
        )
        row = conn.execute("SELECT * FROM search_criteria WHERE id = ?", (cur.lastrowid,)).fetchone()
    return SearchCriteriaOut(**dict(row))


@router.put("/{criteria_id}", response_model=SearchCriteriaOut)
def update_criteria(criteria_id: int, payload: SearchCriteriaIn) -> SearchCriteriaOut:
    now = datetime.now(timezone.utc).isoformat()
    with db.get_db() as conn:
        existing = conn.execute("SELECT id FROM search_criteria WHERE id = ?", (criteria_id,)).fetchone()
        if not existing:
            raise HTTPException(404, "Search criteria not found")
        conn.execute(
            "UPDATE search_criteria SET label=?, keywords=?, target_roles=?, industries=?, locations=?, updated_at=? "
            "WHERE id=?",
            (payload.label, payload.keywords, payload.target_roles, payload.industries,
             payload.locations, now, criteria_id),
        )
        row = conn.execute("SELECT * FROM search_criteria WHERE id = ?", (criteria_id,)).fetchone()
    return SearchCriteriaOut(**dict(row))


@router.delete("/{criteria_id}")
def delete_criteria(criteria_id: int) -> dict[str, str]:
    with db.get_db() as conn:
        conn.execute("DELETE FROM search_criteria WHERE id = ?", (criteria_id,))
    return {"status": "deleted"}
