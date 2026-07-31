import json
from typing import Any, Optional

from app import adzuna_client, config

DISCLAIMER = (
    "This is a rough market estimate based on aggregate Adzuna listing data for this role/location, "
    "not a guaranteed figure. Actual in-hand pay depends on the specific offer's structure "
    "(basic/HRA/bonus split, PF, professional tax, income-tax slab, and company policy)."
)


def _parse_histogram(data: dict) -> list[tuple[float, int]]:
    histogram = data.get("histogram") or {}
    buckets = []
    for k, v in histogram.items():
        try:
            buckets.append((float(k), int(v)))
        except (TypeError, ValueError):
            continue
    buckets.sort(key=lambda b: b[0])
    return buckets


def _percentile(buckets: list[tuple[float, int]], pct: float) -> Optional[float]:
    total = sum(c for _, c in buckets)
    if total == 0:
        return None
    target = total * pct
    cumulative = 0
    for value, count in buckets:
        cumulative += count
        if cumulative >= target:
            return value
    return buckets[-1][0]


def _empty_result(warning: str) -> dict[str, Any]:
    return {
        "ctc_low": None, "ctc_median": None, "ctc_high": None,
        "inhand_low": None, "inhand_high": None,
        "disclaimer": DISCLAIMER, "warning": warning,
        "histogram_json": "{}", "history_json": None,
    }


def estimate_salary(what: str, where: str) -> dict[str, Any]:
    """Pure calculation over Adzuna's aggregate histogram/history data --
    no scraping of individual salary-discussion posts. Interquartile range
    is used (rather than raw min/max) since Adzuna's extreme buckets tend
    to be thin/noisy; this is a simple heuristic, not a rigorous estimate."""
    try:
        histogram_data = adzuna_client.get_salary_histogram(what=what, where=where)
    except adzuna_client.AdzunaConfigError as exc:
        return _empty_result(str(exc))
    except adzuna_client.AdzunaAPIError as exc:
        return _empty_result(f"Adzuna salary lookup failed: {exc}")

    try:
        history_data = adzuna_client.get_salary_history(what=what, where=where)
    except (adzuna_client.AdzunaConfigError, adzuna_client.AdzunaAPIError):
        history_data = {}

    buckets = _parse_histogram(histogram_data)
    warning = None
    ctc_low = ctc_median = ctc_high = None

    if len(buckets) < config.SALARY_MIN_HISTOGRAM_BUCKETS or sum(c for _, c in buckets) == 0:
        warning = "Not enough aggregate salary data for this role/location -- try broadening the search."
    else:
        ctc_low = _percentile(buckets, 0.25)
        ctc_median = _percentile(buckets, 0.50)
        ctc_high = _percentile(buckets, 0.75)

    inhand_low = inhand_high = None
    if ctc_low is not None and ctc_high is not None:
        inhand_low = ctc_low * (1 - config.INHAND_DEDUCTION_PCT_HIGH)
        inhand_high = ctc_high * (1 - config.INHAND_DEDUCTION_PCT_LOW)

    return {
        "ctc_low": ctc_low, "ctc_median": ctc_median, "ctc_high": ctc_high,
        "inhand_low": inhand_low, "inhand_high": inhand_high,
        "disclaimer": DISCLAIMER, "warning": warning,
        "histogram_json": json.dumps(histogram_data), "history_json": json.dumps(history_data),
    }
