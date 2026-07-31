from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

router = APIRouter(prefix="/api/help", tags=["help"])

BASE_DIR = Path(__file__).resolve().parent.parent.parent
MANUAL_PATH = BASE_DIR / "USER_MANUAL.md"


@router.get("/manual", response_class=PlainTextResponse)
def get_manual() -> str:
    if not MANUAL_PATH.exists():
        return "USER_MANUAL.md not found."
    return MANUAL_PATH.read_text(encoding="utf-8")
