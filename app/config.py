import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(ENV_PATH)


def _resolve(path_str: str) -> Path:
    p = Path(path_str)
    return p if p.is_absolute() else (BASE_DIR / p).resolve()


ADZUNA_APP_ID = os.environ.get("ADZUNA_APP_ID", "").strip()
ADZUNA_APP_KEY = os.environ.get("ADZUNA_APP_KEY", "").strip()
APOLLO_API_KEY = os.environ.get("APOLLO_API_KEY", "").strip()
APIFY_API_TOKEN = os.environ.get("APIFY_API_TOKEN", "").strip()

# Not a third-party credential like the three above -- this is a key this app
# generates ITSELF, so external tools (Claude Code, other MCP clients) can
# authenticate INTO this app's /mcp endpoint. See app/mcp_server.py.
APP_KEY = os.environ.get("APP_KEY", "").strip()

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
APIFY_CACHE_TTL_SECONDS = 600
APIFY_RUN_TIMEOUT_SECONDS = 90
APIFY_MAX_ITEMS_PER_SOURCE = 15


def ensure_data_dirs() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    CV_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    TAILORED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# Env vars update_env_values() is allowed to persist. Kept as a fixed
# allowlist (not "any env var"). Note this only governs *this* function --
# it does not mean a route lets a caller set any of these to arbitrary text;
# e.g. APP_KEY is only ever written by regenerate_app_key() below, never from
# free-text user input (see routes/settings.py's KeysIn model).
EDITABLE_KEYS = ("ADZUNA_APP_ID", "ADZUNA_APP_KEY", "APOLLO_API_KEY", "APIFY_API_TOKEN", "APP_KEY")


def update_env_values(updates: dict[str, str]) -> None:
    """Persists the given key/value pairs to .env and applies them immediately
    to this process (os.environ + this module's own globals), so callers that
    read config.ADZUNA_APP_ID etc. at call-time see the new value right away --
    no restart needed. Restricted to EDITABLE_KEYS."""
    updates = {k: v for k, v in updates.items() if k in EDITABLE_KEYS}
    if not updates:
        return

    lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
    written = set()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        key = stripped.split("=", 1)[0].strip() if "=" in stripped and not stripped.startswith("#") else None
        if key in updates:
            new_lines.append(f"{key}={updates[key]}")
            written.add(key)
        else:
            new_lines.append(line)
    for key, value in updates.items():
        if key not in written:
            new_lines.append(f"{key}={value}")
    ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    for key, value in updates.items():
        os.environ[key] = value
        globals()[key] = value


def ensure_app_key() -> str:
    """Generates APP_KEY on first run (persisted to .env) if it doesn't
    already exist. Called once at startup so the app always has one."""
    if not APP_KEY:
        update_env_values({"APP_KEY": secrets.token_urlsafe(32)})
    return APP_KEY


def regenerate_app_key() -> str:
    """Issues a brand-new APP_KEY, invalidating the old one immediately for
    any already-connected MCP client."""
    new_key = secrets.token_urlsafe(32)
    update_env_values({"APP_KEY": new_key})
    return new_key
