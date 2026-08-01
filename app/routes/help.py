import sys
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

router = APIRouter(prefix="/api/help", tags=["help"])

if getattr(sys, "frozen", False):
    # Packaged desktop app: USER_MANUAL.md is bundled as a read-only PyInstaller
    # "data" file (see packaging/navigrad.spec), extracted next to the exe
    # (onedir build) rather than living at this source file's location -- same
    # sys._MEIPASS pattern as app/main.py's public/ static mount.
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).resolve().parent.parent.parent

MANUAL_PATH = BASE_DIR / "USER_MANUAL.md"


@router.get("/manual", response_class=PlainTextResponse)
def get_manual() -> str:
    if not MANUAL_PATH.exists():
        return "USER_MANUAL.md not found."
    return MANUAL_PATH.read_text(encoding="utf-8")
