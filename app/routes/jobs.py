from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app import db, linkedin_export, matching
from app.models import JobSearchResponse, ManualListingIn, ManualListingOut, RankedListing
from app.sources import adzuna_source, manual_source

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _load_criteria(conn, criteria_id: Optional[int]) -> dict:
    if criteria_id is None:
        return {}
    row = conn.execute("SELECT * FROM search_criteria WHERE id = ?", (criteria_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Search criteria not found")
    return dict(row)


@router.get("/search", response_model=JobSearchResponse)
def search_jobs(
    criteria_id: Optional[int] = Query(default=None),
    what: str = "",
    where: str = "",
) -> JobSearchResponse:
    with db.get_db() as conn:
        criteria = _load_criteria(conn, criteria_id)
        if not criteria and (what or where):
            criteria = {"keywords": what, "target_roles": "", "industries": "", "locations": where}

        profile = linkedin_export.load_profile_summary(conn)

        all_listings: list[dict] = []
        warnings: list[str] = []

        for source in (adzuna_source, manual_source):
            listings, source_warnings = source.fetch(conn, criteria)
            all_listings.extend(listings)
            warnings.extend(source_warnings)

    ranked = matching.rank_listings(profile, criteria, all_listings)
    return JobSearchResponse(results=[RankedListing(**r) for r in ranked], warnings=warnings)


@router.get("/manual", response_model=list[ManualListingOut])
def list_manual_listings() -> list[ManualListingOut]:
    with db.get_db() as conn:
        rows = conn.execute("SELECT * FROM manual_listings ORDER BY created_at DESC").fetchall()
        return [ManualListingOut(**dict(r)) for r in rows]


@router.post("/manual", response_model=ManualListingOut)
def create_manual_listing(payload: ManualListingIn) -> ManualListingOut:
    now = datetime.now(timezone.utc).isoformat()
    with db.get_db() as conn:
        cur = conn.execute(
            "INSERT INTO manual_listings (title, company, location, url, description, notes, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (payload.title, payload.company, payload.location, payload.url,
             payload.description, payload.notes, now, now),
        )
        row = conn.execute("SELECT * FROM manual_listings WHERE id = ?", (cur.lastrowid,)).fetchone()
    return ManualListingOut(**dict(row))


@router.put("/manual/{listing_id}", response_model=ManualListingOut)
def update_manual_listing(listing_id: int, payload: ManualListingIn) -> ManualListingOut:
    now = datetime.now(timezone.utc).isoformat()
    with db.get_db() as conn:
        existing = conn.execute("SELECT id FROM manual_listings WHERE id = ?", (listing_id,)).fetchone()
        if not existing:
            raise HTTPException(404, "Listing not found")
        conn.execute(
            "UPDATE manual_listings SET title=?, company=?, location=?, url=?, description=?, notes=?, updated_at=? "
            "WHERE id=?",
            (payload.title, payload.company, payload.location, payload.url,
             payload.description, payload.notes, now, listing_id),
        )
        row = conn.execute("SELECT * FROM manual_listings WHERE id = ?", (listing_id,)).fetchone()
    return ManualListingOut(**dict(row))


@router.delete("/manual/{listing_id}")
def delete_manual_listing(listing_id: int) -> dict[str, str]:
    with db.get_db() as conn:
        conn.execute("DELETE FROM manual_listings WHERE id = ?", (listing_id,))
    return {"status": "deleted"}
