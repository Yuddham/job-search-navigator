"""Client for eliasbiondo/linkedin-mcp-server -- a separate, git-cloned MCP
server (not pip-installable) that searches LinkedIn job listings by driving a
real browser against LinkedIn's own site, optionally signed into the user's
own LinkedIn account for more reliable/complete results.

This is fundamentally different from every other job source in this app and
is treated accordingly:
  - Off by default (config.LINKEDIN_MCP_ENABLED) and never surfaced in the UI
    without the explicit ToS/ban-risk warning shown alongside it in the
    Settings tab's "LinkedIn Account" section.
  - This app never sees or stores a LinkedIn password. "Connecting" launches
    the upstream tool's own --login flow, which opens a real, visible browser
    window on LinkedIn's own login page for the user to authenticate
    themselves -- the same shape as an OAuth "sign in" flow. The resulting
    browser session is persisted by the upstream tool itself, at its own
    fixed path (~/.linkedin-mcp-server/browser-data), not by this app.
  - Deliberately narrow scope: only search_jobs is wired up here, even though
    the upstream server also exposes get_person_profile/search_people/
    get_company_profile/get_company_posts. None of those are used or exposed
    anywhere in this app -- this project's standing rule against scraping
    personal/people data (see root CLAUDE.md's "note on scope") hasn't moved;
    only public job-listing search was requested and approved.
  - Not pip-installable -- requires `git` and `uv` on PATH, installed
    separately by the user. This is a deliberate, disclosed exception to
    "no separate installs," scoped to this one optional, off-by-default,
    higher-risk feature (the upstream tool's own README states scraping
    LinkedIn this way may violate its Terms of Service).
"""
import asyncio
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

from app import config

REPO_URL = "https://github.com/eliasbiondo/linkedin-mcp-server.git"
REPO_DIR = config.BASE_DIR / "data" / "linkedin-mcp-server"
SESSION_MARKER = Path.home() / ".linkedin-mcp-server" / "browser-data"


class LinkedInMcpError(Exception):
    pass


def tooling_available() -> bool:
    return shutil.which("git") is not None and shutil.which("uv") is not None


def is_installed() -> bool:
    return (REPO_DIR / "pyproject.toml").exists()


def is_connected() -> bool:
    """Best-effort only: checks whether the upstream tool's browser profile
    directory exists at all, not whether it holds a genuinely valid LinkedIn
    session -- that would require decrypting the browser's cookie store,
    disproportionate for a status indicator. The UI hedges its wording
    accordingly rather than asserting a precise "connected" guarantee."""
    return SESSION_MARKER.exists()


def status() -> dict[str, bool]:
    return {
        "tooling_available": tooling_available(),
        "installed": is_installed(),
        "connected": is_connected(),
        "enabled": config.LINKEDIN_MCP_ENABLED,
    }


def _run(args: list[str], cwd: Optional[Path] = None, timeout: int = 900) -> None:
    result = subprocess.run(args, cwd=str(cwd) if cwd else None, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise LinkedInMcpError(f"Command failed ({' '.join(args)}): {(result.stderr or result.stdout)[-2000:]}")


def install() -> None:
    """Clones the repo and installs it (including its own Patchright browser
    binary) via `uv`. One-time, a few hundred MB, requires internet."""
    if not tooling_available():
        raise LinkedInMcpError(
            "This feature needs 'git' and 'uv' installed separately -- see "
            "https://git-scm.com/downloads and https://docs.astral.sh/uv/getting-started/installation/. "
            "Neither is bundled with Navigrad since this is an optional, "
            "off-by-default feature relying on a third-party tool that isn't pip-installable."
        )
    if not is_installed():
        REPO_DIR.parent.mkdir(parents=True, exist_ok=True)
        _run(["git", "clone", REPO_URL, str(REPO_DIR)])
    _run(["uv", "sync"], cwd=REPO_DIR)
    _run(["uv", "run", "patchright", "install"], cwd=REPO_DIR)


def start_login() -> None:
    """Launches the interactive login flow -- opens a real, visible browser
    window on LinkedIn's own site for the user to log in themselves. Runs
    detached (fire-and-forget); the caller polls is_connected() afterward."""
    install()  # no-ops if already installed
    kwargs: dict[str, Any] = {"cwd": str(REPO_DIR)}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(["uv", "run", "linkedin-mcp-server", "--login"], **kwargs)


async def _search_jobs_async(keyword: str, location: str, max_pages: int) -> list[dict]:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(command="uv", args=["run", "linkedin-mcp-server"], cwd=str(REPO_DIR))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "search_jobs",
                {"keywords": keyword, "location": location or None, "max_pages": max_pages},
            )
            if result.is_error:
                text = result.content[0].text if result.content else "unknown error"
                raise LinkedInMcpError(f"LinkedIn search failed: {text}")
            return result.structured_content or {}


def search_jobs(keyword: str, location: str = "", max_pages: int = 1) -> list[dict]:
    """Searches LinkedIn job listings. Does NOT require is_connected() to be
    true -- LinkedIn's public search results are often reachable without a
    session -- but results are more reliable and complete once connected,
    which is why the Settings tab's flow leads with "Connect" regardless."""
    if not config.LINKEDIN_MCP_ENABLED:
        return []
    if not is_installed():
        raise LinkedInMcpError("LinkedIn account search isn't installed yet -- connect it in Settings first.")

    try:
        data = asyncio.run(_search_jobs_async(keyword, location, max_pages))
    except LinkedInMcpError:
        raise
    except BaseException as exc:  # anyio wraps errors from the async context managers in an ExceptionGroup
        inner = exc.exceptions[0] if isinstance(exc, BaseExceptionGroup) else exc
        while isinstance(inner, BaseExceptionGroup):
            inner = inner.exceptions[0]
        if isinstance(inner, LinkedInMcpError):
            raise inner from exc
        raise LinkedInMcpError(f"LinkedIn search failed: {inner}") from exc
    jobs = ((data.get("sections") or {}).get("page_1") or {}).get("jobs") or []

    results = []
    for job in jobs:
        if not isinstance(job, dict) or not job.get("title"):
            continue
        results.append({
            "source": "linkedin_account",
            "external_id": job.get("job_id"),
            "title": job.get("title") or "",
            "company": job.get("company"),
            "location": job.get("location"),
            "description": None,
            "url": job.get("job_url"),
            "salary_min": None,
            "salary_max": None,
            "category": None,
            "posted_at": None,
        })
    return results
