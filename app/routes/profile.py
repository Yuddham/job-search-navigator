from fastapi import APIRouter, File, HTTPException, UploadFile

from app import db, linkedin_export
from app.models import ProfileSummary, ProfileUploadResponse

router = APIRouter(prefix="/api/profile", tags=["profile"])


@router.post("/upload", response_model=ProfileUploadResponse)
async def upload_profile(file: UploadFile = File(...)) -> ProfileUploadResponse:
    if not (file.filename or "").lower().endswith(".zip"):
        raise HTTPException(
            400,
            "Please upload the .zip file from LinkedIn's 'Download your data' export.",
        )
    content = await file.read()
    parsed = linkedin_export.parse_export(content)

    with db.get_db() as conn:
        save_result = linkedin_export.save_profile(conn, parsed)
        profile = linkedin_export.load_profile_summary(conn)

    profile["warnings"] = save_result["warnings"]
    return ProfileUploadResponse(
        summary=ProfileSummary(**profile),
        counts=save_result["counts"],
        warnings=save_result["warnings"],
    )


@router.get("", response_model=ProfileSummary)
def get_profile() -> ProfileSummary:
    with db.get_db() as conn:
        profile = linkedin_export.load_profile_summary(conn)
    profile["warnings"] = []
    return ProfileSummary(**profile)


@router.delete("")
def delete_profile() -> dict[str, str]:
    with db.get_db() as conn:
        linkedin_export.clear_profile(conn)
    return {"status": "deleted"}
