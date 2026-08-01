from contextlib import AsyncExitStack
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import JSONResponse

from app import config, db
from app.mcp_server import mcp_server

BASE_DIR = Path(__file__).resolve().parent.parent
LANDING_PAGE_PATH = BASE_DIR / "public" / "landing" / "hud" / "v5-scan" / "hero.html"

app = FastAPI(title="Job Search Navigator")
_mcp_exit_stack: AsyncExitStack | None = None


class BearerAuthMiddleware:
    """Guards the /mcp mount with the app's own generated App Key (Settings
    tab) -- a plain shared-secret check, not the mcp SDK's OAuth machinery,
    since this is a local single-user tool with one static key, not a
    multi-tenant remote server."""

    def __init__(self, asgi_app) -> None:
        self.asgi_app = asgi_app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.asgi_app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        auth_header = headers.get(b"authorization", b"").decode("latin-1")
        token = auth_header[7:] if auth_header.lower().startswith("bearer ") else ""

        if not config.APP_KEY or token != config.APP_KEY:
            response = JSONResponse({"error": "Unauthorized -- missing or invalid App Key"}, status_code=401)
            await response(scope, receive, send)
            return

        await self.asgi_app(scope, receive, send)


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    # The v5-scan radar landing page is the app's default home page; the
    # actual app (formerly served at "/") is still reachable at /index.html.
    return FileResponse(LANDING_PAGE_PATH)


@app.on_event("startup")
async def on_startup() -> None:
    global _mcp_exit_stack
    config.ensure_data_dirs()
    config.ensure_app_key()
    db.init_db()

    _mcp_exit_stack = AsyncExitStack()
    await _mcp_exit_stack.enter_async_context(mcp_server.session_manager.run())


@app.on_event("shutdown")
async def on_shutdown() -> None:
    if _mcp_exit_stack is not None:
        await _mcp_exit_stack.aclose()


def _include_routers() -> None:
    from app.routes import profile, criteria, jobs, contacts, cv, tailoring, salary, apollo, design, settings, help as help_route

    app.include_router(profile.router)
    app.include_router(criteria.router)
    app.include_router(jobs.router)
    app.include_router(contacts.router)
    app.include_router(cv.router)
    app.include_router(tailoring.router)
    app.include_router(salary.router)
    app.include_router(apollo.router)
    app.include_router(design.router)
    app.include_router(settings.router)
    app.include_router(help_route.router)


_include_routers()

# streamable_http_path="/" so mounting this sub-app at "/mcp" below yields a
# single clean "/mcp" endpoint, not "/mcp/mcp".
app.mount("/mcp", BearerAuthMiddleware(mcp_server.streamable_http_app(streamable_http_path="/")))

app.mount("/", StaticFiles(directory=str(BASE_DIR / "public"), html=True), name="static")
