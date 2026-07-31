from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app import db
from app.models import ContactIn, ContactOut, JobLeadIn, JobLeadOut

router = APIRouter(prefix="/api", tags=["contacts"])


# ---- Contacts ----

@router.get("/contacts", response_model=list[ContactOut])
def list_contacts() -> list[ContactOut]:
    with db.get_db() as conn:
        rows = conn.execute("SELECT * FROM contacts ORDER BY updated_at DESC").fetchall()
        return [ContactOut(**dict(r)) for r in rows]


@router.post("/contacts", response_model=ContactOut)
def create_contact(payload: ContactIn) -> ContactOut:
    now = datetime.now(timezone.utc).isoformat()
    with db.get_db() as conn:
        cur = conn.execute(
            "INSERT INTO contacts (name, linkedin_url, company, email, phone, notes, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (payload.name, payload.linkedin_url, payload.company, payload.email, payload.phone,
             payload.notes, payload.status, now, now),
        )
        row = conn.execute("SELECT * FROM contacts WHERE id = ?", (cur.lastrowid,)).fetchone()
    return ContactOut(**dict(row))


@router.put("/contacts/{contact_id}", response_model=ContactOut)
def update_contact(contact_id: int, payload: ContactIn) -> ContactOut:
    now = datetime.now(timezone.utc).isoformat()
    with db.get_db() as conn:
        existing = conn.execute("SELECT id FROM contacts WHERE id = ?", (contact_id,)).fetchone()
        if not existing:
            raise HTTPException(404, "Contact not found")
        conn.execute(
            "UPDATE contacts SET name=?, linkedin_url=?, company=?, email=?, phone=?, notes=?, status=?, "
            "updated_at=? WHERE id=?",
            (payload.name, payload.linkedin_url, payload.company, payload.email, payload.phone,
             payload.notes, payload.status, now, contact_id),
        )
        row = conn.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,)).fetchone()
    return ContactOut(**dict(row))


@router.delete("/contacts/{contact_id}")
def delete_contact(contact_id: int) -> dict[str, str]:
    with db.get_db() as conn:
        conn.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
    return {"status": "deleted"}


# ---- Job leads (postings found by browsing manually, e.g. on LinkedIn) ----

@router.get("/leads", response_model=list[JobLeadOut])
def list_leads() -> list[JobLeadOut]:
    with db.get_db() as conn:
        rows = conn.execute("SELECT * FROM job_leads ORDER BY updated_at DESC").fetchall()
        return [JobLeadOut(**dict(r)) for r in rows]


@router.post("/leads", response_model=JobLeadOut)
def create_lead(payload: JobLeadIn) -> JobLeadOut:
    now = datetime.now(timezone.utc).isoformat()
    with db.get_db() as conn:
        cur = conn.execute(
            "INSERT INTO job_leads (job_url, company, recruiter_name, recruiter_contact_id, notes, status, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (payload.job_url, payload.company, payload.recruiter_name, payload.recruiter_contact_id,
             payload.notes, payload.status, now, now),
        )
        row = conn.execute("SELECT * FROM job_leads WHERE id = ?", (cur.lastrowid,)).fetchone()
    return JobLeadOut(**dict(row))


@router.put("/leads/{lead_id}", response_model=JobLeadOut)
def update_lead(lead_id: int, payload: JobLeadIn) -> JobLeadOut:
    now = datetime.now(timezone.utc).isoformat()
    with db.get_db() as conn:
        existing = conn.execute("SELECT id FROM job_leads WHERE id = ?", (lead_id,)).fetchone()
        if not existing:
            raise HTTPException(404, "Lead not found")
        conn.execute(
            "UPDATE job_leads SET job_url=?, company=?, recruiter_name=?, recruiter_contact_id=?, notes=?, "
            "status=?, updated_at=? WHERE id=?",
            (payload.job_url, payload.company, payload.recruiter_name, payload.recruiter_contact_id,
             payload.notes, payload.status, now, lead_id),
        )
        row = conn.execute("SELECT * FROM job_leads WHERE id = ?", (lead_id,)).fetchone()
    return JobLeadOut(**dict(row))


@router.delete("/leads/{lead_id}")
def delete_lead(lead_id: int) -> dict[str, str]:
    with db.get_db() as conn:
        conn.execute("DELETE FROM job_leads WHERE id = ?", (lead_id,))
    return {"status": "deleted"}
