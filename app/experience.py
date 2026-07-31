import re
from datetime import date
from typing import Optional

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

_MONTH_YEAR_RE = re.compile(r"([a-zA-Z]{3,})?\s*(\d{4})")

# Seniority bands are a simple, transparent heuristic on total career span --
# not a precise mapping, just enough to make the Adzuna query more specific
# than a bare job title. Tweak the thresholds directly if they feel off.
SENIORITY_BANDS = [
    (0, 2, "entry level"),
    (2, 5, "mid level"),
    (5, 10, "senior"),
    (10, 100, "lead"),
]


def _parse_month_year(text: str) -> Optional[date]:
    if not text:
        return None
    cleaned = text.strip().lower()
    if cleaned in ("present", "current", "now", ""):
        return date.today()
    match = _MONTH_YEAR_RE.search(cleaned)
    if not match:
        return None
    month_str, year_str = match.groups()
    year = int(year_str)
    month = 1
    if month_str:
        month = MONTHS.get(month_str[:3], 1)
    try:
        return date(year, month, 1)
    except ValueError:
        return None


def estimate_years_of_experience(positions: list[dict]) -> Optional[float]:
    """Simple heuristic: earliest position start to latest position end (or
    today, if any position is ongoing). Doesn't account for career gaps --
    a rough proxy, not a precise calculation."""
    starts = []
    ends = []
    for p in positions or []:
        start = _parse_month_year(p.get("started_on") or "")
        end = _parse_month_year(p.get("ended_on") or "") or date.today()
        if start:
            starts.append(start)
            ends.append(end)
    if not starts:
        return None
    span_days = (max(ends) - min(starts)).days
    return round(max(span_days, 0) / 365.25, 1)


def infer_seniority_label(positions: list[dict]) -> Optional[str]:
    years = estimate_years_of_experience(positions)
    if years is None:
        return None
    for low, high, label in SENIORITY_BANDS:
        if low <= years < high:
            return label
    return None
