import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app import config, db, job_fetch, keyword_gap
from app.models import (
    GenerateTailoredIn,
    KeywordGap,
    KeywordMatch,
    TailoringAnalyzeIn,
    TailoringReportOut,
    TargetJobFetchIn,
    TargetJobManualIn,
    TargetJobOut,
)

router = APIRouter(prefix="/api", tags=["tailoring"])


def _row_to_target_job(r) -> TargetJobOut:
    return TargetJobOut(
        id=r["id"], source_url=r["source_url"], source_type=r["source_type"],
        fetch_status=r["fetch_status"], fetch_warning=r["fetch_warning"],
        company=r["company"], title=r["title"], location=r["location"],
        jd_text=r["jd_text"], fetched_at=r["fetched_at"],
    )


@router.post("/target-jobs/fetch-url", response_model=TargetJobOut)
def fetch_target_job(payload: TargetJobFetchIn) -> TargetJobOut:
    result = job_fetch.fetch_job_posting(payload.url)
    now = datetime.now(timezone.utc).isoformat()
    with db.get_db() as conn:
        cur = conn.execute(
            "INSERT INTO target_jobs (source_url, source_type, fetch_status, fetch_warning, company, title, "
            "location, jd_text, fetched_at) VALUES (?, 'url_fetch', ?, ?, ?, ?, ?, ?, ?)",
            (payload.url, result["status"], result.get("warning"), result.get("company"),
             result.get("title"), result.get("location"), result.get("jd_text"), now),
        )
        row = conn.execute("SELECT * FROM target_jobs WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _row_to_target_job(row)


@router.post("/target-jobs/manual", response_model=TargetJobOut)
def create_target_job_manual(payload: TargetJobManualIn) -> TargetJobOut:
    now = datetime.now(timezone.utc).isoformat()
    with db.get_db() as conn:
        cur = conn.execute(
            "INSERT INTO target_jobs (source_url, source_type, fetch_status, fetch_warning, company, title, "
            "location, jd_text, fetched_at) VALUES (?, 'manual_paste', 'manual', NULL, ?, ?, ?, ?, ?)",
            (payload.source_url or None, payload.company, payload.title, payload.location,
             payload.jd_text, now),
        )
        row = conn.execute("SELECT * FROM target_jobs WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _row_to_target_job(row)


@router.get("/target-jobs", response_model=list[TargetJobOut])
def list_target_jobs() -> list[TargetJobOut]:
    with db.get_db() as conn:
        rows = conn.execute("SELECT * FROM target_jobs ORDER BY fetched_at DESC").fetchall()
    return [_row_to_target_job(r) for r in rows]


@router.get("/target-jobs/{job_id}", response_model=TargetJobOut)
def get_target_job(job_id: int) -> TargetJobOut:
    with db.get_db() as conn:
        row = conn.execute("SELECT * FROM target_jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Target job not found")
    return _row_to_target_job(row)


@router.delete("/target-jobs/{job_id}")
def delete_target_job(job_id: int) -> dict[str, str]:
    with db.get_db() as conn:
        conn.execute("DELETE FROM target_jobs WHERE id = ?", (job_id,))
    return {"status": "deleted"}


def _row_to_tailoring_report(r) -> TailoringReportOut:
    return TailoringReportOut(
        id=r["id"], cv_document_id=r["cv_document_id"], target_job_id=r["target_job_id"],
        created_at=r["created_at"],
        matched_keywords=[KeywordMatch(**m) for m in json.loads(r["matched_keywords_json"] or "[]")],
        missing_keywords=[KeywordGap(**m) for m in json.loads(r["missing_keywords_json"] or "[]")],
        match_score=r["match_score"] or 0.0,
        key_skills_line=r["key_skills_line"],
        generated_files=json.loads(r["generated_files_json"] or "{}"),
    )


@router.post("/tailoring/analyze", response_model=TailoringReportOut)
def analyze(payload: TailoringAnalyzeIn) -> TailoringReportOut:
    with db.get_db() as conn:
        cv_row = conn.execute("SELECT * FROM cv_documents WHERE id = ?", (payload.cv_document_id,)).fetchone()
        if not cv_row:
            raise HTTPException(404, "CV not found")
        job_row = conn.execute("SELECT * FROM target_jobs WHERE id = ?", (payload.target_job_id,)).fetchone()
        if not job_row:
            raise HTTPException(404, "Target job not found")

        cv_sections = json.loads(cv_row["sections_json"] or "{}")
        gap_result = keyword_gap.compare_cv_to_jd(
            cv_row["raw_text"], cv_sections, job_row["jd_text"] or "", config.KEYWORD_GAP_TOP_N,
        )

        now = datetime.now(timezone.utc).isoformat()
        cur = conn.execute(
            "INSERT INTO cv_tailoring_reports (cv_document_id, target_job_id, created_at, matched_keywords_json, "
            "missing_keywords_json, match_score, generated_files_json, key_skills_line) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (payload.cv_document_id, payload.target_job_id, now,
             json.dumps(gap_result["matched_keywords"]), json.dumps(gap_result["missing_keywords"]),
             gap_result["match_score"], json.dumps({}), gap_result["key_skills_line"]),
        )
        row = conn.execute("SELECT * FROM cv_tailoring_reports WHERE id = ?", (cur.lastrowid,)).fetchone()
    return _row_to_tailoring_report(row)


@router.get("/tailoring/{report_id}", response_model=TailoringReportOut)
def get_tailoring_report(report_id: int) -> TailoringReportOut:
    with db.get_db() as conn:
        row = conn.execute("SELECT * FROM cv_tailoring_reports WHERE id = ?", (report_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Tailoring report not found")
    return _row_to_tailoring_report(row)


@router.get("/tailoring", response_model=list[TailoringReportOut])
def list_tailoring_reports(
    cv_document_id: Optional[int] = None, target_job_id: Optional[int] = None,
) -> list[TailoringReportOut]:
    query = "SELECT * FROM cv_tailoring_reports WHERE 1=1"
    params: list = []
    if cv_document_id is not None:
        query += " AND cv_document_id = ?"
        params.append(cv_document_id)
    if target_job_id is not None:
        query += " AND target_job_id = ?"
        params.append(target_job_id)
    query += " ORDER BY created_at DESC"
    with db.get_db() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_tailoring_report(r) for r in rows]


@router.post("/tailoring/{report_id}/generate", response_model=TailoringReportOut)
def generate_tailored(report_id: int, payload: GenerateTailoredIn) -> TailoringReportOut:
    with db.get_db() as conn:
        report_row = conn.execute("SELECT * FROM cv_tailoring_reports WHERE id = ?", (report_id,)).fetchone()
        if not report_row:
            raise HTTPException(404, "Tailoring report not found")
        cv_row = conn.execute(
            "SELECT * FROM cv_documents WHERE id = ?", (report_row["cv_document_id"],),
        ).fetchone()
        if not cv_row:
            raise HTTPException(404, "CV not found")

        cv_sections = json.loads(cv_row["sections_json"] or "{}")
        matched = json.loads(report_row["matched_keywords_json"] or "[]")
        missing = json.loads(report_row["missing_keywords_json"] or "[]")
        key_skills_line = report_row["key_skills_line"]

        config.ensure_data_dirs()
        generated_files = json.loads(report_row["generated_files_json"] or "{}")

        if payload.format == "markdown":
            content = keyword_gap.generate_tailored_markdown(cv_sections, matched, missing, key_skills_line)
            filename = f"tailored_{report_id}.md"
            (config.TAILORED_OUTPUT_DIR / filename).write_text(content, encoding="utf-8")
            generated_files["markdown"] = filename
        else:
            filename = f"tailored_{report_id}.docx"
            keyword_gap.generate_tailored_docx(
                cv_sections, matched, missing, key_skills_line, config.TAILORED_OUTPUT_DIR / filename,
            )
            generated_files["docx"] = filename

        conn.execute(
            "UPDATE cv_tailoring_reports SET generated_files_json = ? WHERE id = ?",
            (json.dumps(generated_files), report_id),
        )
        row = conn.execute("SELECT * FROM cv_tailoring_reports WHERE id = ?", (report_id,)).fetchone()
    return _row_to_tailoring_report(row)


@router.get("/tailoring/{report_id}/download")
def download_tailored(report_id: int, format: str):
    with db.get_db() as conn:
        row = conn.execute("SELECT * FROM cv_tailoring_reports WHERE id = ?", (report_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Tailoring report not found")
    generated_files = json.loads(row["generated_files_json"] or "{}")
    filename = generated_files.get(format)
    if not filename:
        raise HTTPException(404, f"No generated {format} file for this report yet -- call /generate first.")
    path = config.TAILORED_OUTPUT_DIR / filename
    if not path.exists():
        raise HTTPException(404, "Generated file is missing on disk.")
    return FileResponse(str(path), filename=filename)
