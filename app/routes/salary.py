from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter

from app import adzuna_client, config, db, salary_estimator
from app.models import SalaryEstimateOut

router = APIRouter(prefix="/api/salary", tags=["salary"])


def _row_to_estimate(r) -> SalaryEstimateOut:
    return SalaryEstimateOut(
        id=r["id"], role_query=r["role_query"], location_query=r["location_query"],
        created_at=r["created_at"], ctc_low=r["ctc_low"], ctc_median=r["ctc_median"], ctc_high=r["ctc_high"],
        inhand_low=r["inhand_low"], inhand_high=r["inhand_high"], disclaimer=r["disclaimer"], warning=None,
    )


@router.get("/estimate", response_model=SalaryEstimateOut)
def get_estimate(what: str = "", where: str = "", target_job_id: Optional[int] = None) -> SalaryEstimateOut:
    with db.get_db() as conn:
        if target_job_id is not None:
            job = conn.execute("SELECT * FROM target_jobs WHERE id = ?", (target_job_id,)).fetchone()
            if job:
                what = what or job["title"] or ""
                where = where or job["location"] or ""

        result = salary_estimator.estimate_salary(what, where)
        now = datetime.now(timezone.utc).isoformat()
        cur = conn.execute(
            "INSERT INTO salary_estimates (target_job_id, role_query, location_query, created_at, histogram_json, "
            "history_json, ctc_low, ctc_median, ctc_high, deduction_pct_low, deduction_pct_high, inhand_low, "
            "inhand_high, disclaimer) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (target_job_id, what, where, now, result["histogram_json"], result["history_json"],
             result["ctc_low"], result["ctc_median"], result["ctc_high"],
             config.INHAND_DEDUCTION_PCT_LOW, config.INHAND_DEDUCTION_PCT_HIGH,
             result["inhand_low"], result["inhand_high"], result["disclaimer"]),
        )
        row = conn.execute("SELECT * FROM salary_estimates WHERE id = ?", (cur.lastrowid,)).fetchone()

    out = _row_to_estimate(row)
    out.warning = result.get("warning")
    return out


@router.get("/history")
def get_history(what: str = "", where: str = "", months: int = 6) -> dict:
    try:
        data = adzuna_client.get_salary_history(what=what, where=where, months=months)
        return {"data": data, "warning": None}
    except adzuna_client.AdzunaConfigError as exc:
        return {"data": None, "warning": str(exc)}
    except adzuna_client.AdzunaAPIError as exc:
        return {"data": None, "warning": f"Adzuna salary history failed: {exc}"}


@router.get("/estimates", response_model=list[SalaryEstimateOut])
def list_estimates() -> list[SalaryEstimateOut]:
    with db.get_db() as conn:
        rows = conn.execute("SELECT * FROM salary_estimates ORDER BY created_at DESC").fetchall()
    return [_row_to_estimate(r) for r in rows]
