from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import config, db

BASE_DIR = Path(__file__).resolve().parent.parent
LANDING_PAGE_PATH = BASE_DIR / "public" / "landing" / "hud" / "v5-scan" / "hero.html"

app = FastAPI(title="Job Search Navigator")


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    # The v5-scan radar landing page is the app's default home page; the
    # actual app (formerly served at "/") is still reachable at /index.html.
    return FileResponse(LANDING_PAGE_PATH)


@app.on_event("startup")
def on_startup() -> None:
    config.ensure_data_dirs()
    db.init_db()


def _include_routers() -> None:
    from app.routes import profile, criteria, jobs, contacts, cv, tailoring, salary, apollo, design, help as help_route

    app.include_router(profile.router)
    app.include_router(criteria.router)
    app.include_router(jobs.router)
    app.include_router(contacts.router)
    app.include_router(cv.router)
    app.include_router(tailoring.router)
    app.include_router(salary.router)
    app.include_router(apollo.router)
    app.include_router(design.router)
    app.include_router(help_route.router)


_include_routers()

app.mount("/", StaticFiles(directory=str(BASE_DIR / "public"), html=True), name="static")
