import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile

from app import ats_checker, config, cv_parser, db
from app.models import AtsChecklistItem, AtsReport, CvDocumentOut, CvUploadResponse

router = APIRouter(prefix="/api/cv", tags=["cv"])


def _detect_file_type(filename: str) -> Optional[str]:
    lower = (filename or "").lower()
    if lower.endswith(".pdf"):
        return "pdf"
    if lower.endswith(".docx"):
        return "docx"
    return None


def _row_to_cv_document(r) -> CvDocumentOut:
    return CvDocumentOut(
        id=r["id"],
        original_filename=r["original_filename"],
        file_type=r["file_type"],
        uploaded_at=r["uploaded_at"],
        is_active=bool(r["is_active"]),
        sections=json.loads(r["sections_json"] or "{}"),
        warnings=json.loads(r["parse_warnings_json"] or "[]"),
    )


def _row_to_ats_report(r) -> AtsReport:
    return AtsReport(
        id=r["id"],
        cv_document_id=r["cv_document_id"],
        checked_at=r["checked_at"],
        overall_score=r["overall_score"],
        checklist=[AtsChecklistItem(**c) for c in json.loads(r["checklist_json"] or "[]")],
        summary=r["summary"],
    )


@router.post("/upload", response_model=CvUploadResponse)
async def upload_cv(file: UploadFile = File(...)) -> CvUploadResponse:
    file_type = _detect_file_type(file.filename or "")
    if not file_type:
        raise HTTPException(400, "Please upload a .pdf or .docx CV file.")

    content = await file.read()
    if len(content) > config.CV_MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(400, f"File is larger than the {config.CV_MAX_UPLOAD_MB}MB limit.")

    parsed = cv_parser.parse_cv(content, file_type)

    config.ensure_data_dirs()
    stored_filename = f"{uuid.uuid4().hex}.{file_type}"
    (config.CV_UPLOAD_DIR / stored_filename).write_bytes(content)

    uploaded_at = datetime.now(timezone.utc).isoformat()
    ats_result = ats_checker.run_ats_checks(
        parsed["raw_text"], parsed["sections"], parsed["layout_meta"], file.filename or "",
    )
    checked_at = datetime.now(timezone.utc).isoformat()

    with db.get_db() as conn:
        conn.execute("UPDATE cv_documents SET is_active = 0")
        cur = conn.execute(
            "INSERT INTO cv_documents (original_filename, stored_filename, file_type, uploaded_at, raw_text, "
            "sections_json, layout_meta_json, parse_warnings_json, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)",
            (file.filename, stored_filename, file_type, uploaded_at, parsed["raw_text"],
             json.dumps(parsed["sections"]), json.dumps(parsed["layout_meta"]), json.dumps(parsed["warnings"])),
        )
        cv_document_id = cur.lastrowid

        cur2 = conn.execute(
            "INSERT INTO cv_ats_reports (cv_document_id, checked_at, overall_score, checklist_json, summary) "
            "VALUES (?, ?, ?, ?, ?)",
            (cv_document_id, checked_at, ats_result["overall_score"],
             json.dumps(ats_result["checklist"]), ats_result["summary"]),
        )
        ats_report_id = cur2.lastrowid

    cv_document = CvDocumentOut(
        id=cv_document_id, original_filename=file.filename or "", file_type=file_type,
        uploaded_at=uploaded_at, is_active=True, sections=parsed["sections"], warnings=parsed["warnings"],
    )
    ats_report = AtsReport(
        id=ats_report_id, cv_document_id=cv_document_id, checked_at=checked_at,
        overall_score=ats_result["overall_score"],
        checklist=[AtsChecklistItem(**c) for c in ats_result["checklist"]],
        summary=ats_result["summary"],
    )
    return CvUploadResponse(cv_document=cv_document, ats_report=ats_report)


@router.get("", response_model=list[CvDocumentOut])
def list_cvs() -> list[CvDocumentOut]:
    with db.get_db() as conn:
        rows = conn.execute("SELECT * FROM cv_documents ORDER BY uploaded_at DESC").fetchall()
    return [_row_to_cv_document(r) for r in rows]


@router.get("/{cv_id}", response_model=CvDocumentOut)
def get_cv(cv_id: int) -> CvDocumentOut:
    with db.get_db() as conn:
        r = conn.execute("SELECT * FROM cv_documents WHERE id = ?", (cv_id,)).fetchone()
    if not r:
        raise HTTPException(404, "CV not found")
    return _row_to_cv_document(r)


@router.get("/{cv_id}/ats-report", response_model=AtsReport)
def get_latest_ats_report(cv_id: int) -> AtsReport:
    with db.get_db() as conn:
        r = conn.execute(
            "SELECT * FROM cv_ats_reports WHERE cv_document_id = ? ORDER BY checked_at DESC LIMIT 1", (cv_id,),
        ).fetchone()
    if not r:
        raise HTTPException(404, "No ATS report found for this CV")
    return _row_to_ats_report(r)


@router.post("/{cv_id}/rerun-ats", response_model=AtsReport)
def rerun_ats(cv_id: int) -> AtsReport:
    with db.get_db() as conn:
        doc = conn.execute("SELECT * FROM cv_documents WHERE id = ?", (cv_id,)).fetchone()
        if not doc:
            raise HTTPException(404, "CV not found")
        sections = json.loads(doc["sections_json"] or "{}")
        layout_meta = json.loads(doc["layout_meta_json"] or "{}")
        ats_result = ats_checker.run_ats_checks(doc["raw_text"], sections, layout_meta, doc["original_filename"])
        checked_at = datetime.now(timezone.utc).isoformat()
        cur = conn.execute(
            "INSERT INTO cv_ats_reports (cv_document_id, checked_at, overall_score, checklist_json, summary) "
            "VALUES (?, ?, ?, ?, ?)",
            (cv_id, checked_at, ats_result["overall_score"], json.dumps(ats_result["checklist"]), ats_result["summary"]),
        )
        report_id = cur.lastrowid
    return AtsReport(
        id=report_id, cv_document_id=cv_id, checked_at=checked_at, overall_score=ats_result["overall_score"],
        checklist=[AtsChecklistItem(**c) for c in ats_result["checklist"]], summary=ats_result["summary"],
    )


@router.post("/{cv_id}/activate")
def activate_cv(cv_id: int) -> dict[str, str]:
    with db.get_db() as conn:
        existing = conn.execute("SELECT id FROM cv_documents WHERE id = ?", (cv_id,)).fetchone()
        if not existing:
            raise HTTPException(404, "CV not found")
        conn.execute("UPDATE cv_documents SET is_active = 0")
        conn.execute("UPDATE cv_documents SET is_active = 1 WHERE id = ?", (cv_id,))
    return {"status": "activated"}


@router.delete("/{cv_id}")
def delete_cv(cv_id: int) -> dict[str, str]:
    with db.get_db() as conn:
        row = conn.execute("SELECT stored_filename FROM cv_documents WHERE id = ?", (cv_id,)).fetchone()
        conn.execute("DELETE FROM cv_documents WHERE id = ?", (cv_id,))
    if row and row["stored_filename"]:
        try:
            (config.CV_UPLOAD_DIR / row["stored_filename"]).unlink(missing_ok=True)
        except OSError:
            pass
    return {"status": "deleted"}
