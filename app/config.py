import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _resolve(path_str: str) -> Path:
    p = Path(path_str)
    return p if p.is_absolute() else (BASE_DIR / p).resolve()


ADZUNA_APP_ID = os.environ.get("ADZUNA_APP_ID", "").strip()
ADZUNA_APP_KEY = os.environ.get("ADZUNA_APP_KEY", "").strip()
APOLLO_API_KEY = os.environ.get("APOLLO_API_KEY", "").strip()

PORT = int(os.environ.get("PORT", "8000"))
DB_PATH = _resolve(os.environ.get("DB_PATH", "./data/job_search.db"))
CV_UPLOAD_DIR = _resolve(os.environ.get("CV_UPLOAD_DIR", "./data/uploads/cv"))
TAILORED_OUTPUT_DIR = _resolve(os.environ.get("TAILORED_OUTPUT_DIR", "./data/tailored"))

CV_MAX_UPLOAD_MB = 10
ATS_MIN_TEXT_CHARS_PER_PAGE = 50
ATS_MIN_WORD_COUNT = 150
ATS_MAX_WORD_COUNT = 1200

JOB_FETCH_TIMEOUT_SECONDS = 10
JOB_FETCH_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
JOB_FETCH_MIN_TEXT_CHARS = 200

KEYWORD_GAP_TOP_N = 40

INHAND_DEDUCTION_PCT_LOW = float(os.environ.get("INHAND_DEDUCTION_PCT_LOW", "0.20"))
INHAND_DEDUCTION_PCT_HIGH = float(os.environ.get("INHAND_DEDUCTION_PCT_HIGH", "0.30"))
SALARY_MIN_HISTOGRAM_BUCKETS = 3

ADZUNA_CACHE_TTL_SECONDS = 600
APOLLO_CACHE_TTL_SECONDS = 600


def ensure_data_dirs() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    CV_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    TAILORED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
