"""Exposes a curated, read-only slice of this app's own data to external LLM
clients (Claude Code or any other MCP-compatible client) over the Model
Context Protocol's Streamable HTTP transport. Mounted at /mcp in main.py,
gated by the app's own generated App Key (see config.APP_KEY / the Settings
tab) via a plain Bearer-token check -- not the same thing as the Adzuna/
Apollo/Apify keys, which authenticate this app *outward* to those services.
This authenticates other tools *inward* into this app.

Deliberately read-only and reuses the same functions the REST API/UI already
call (app.routes.jobs.search_jobs, app.routes.salary.get_estimate, etc.) so
there is exactly one implementation of each piece of business logic, not a
parallel copy for MCP callers.
"""
from mcp.server.mcpserver import MCPServer

from app import db, linkedin_export

mcp_server = MCPServer(
    name="navigrad",
    instructions=(
        "Local job-search assistant for the Indian market. Ranks live job listings "
        "(Adzuna/Apollo/Apify, plus manually-added listings) against the user's "
        "LinkedIn-derived profile, and estimates CTC/in-hand salary from Adzuna's "
        "aggregate data. Read-only from here -- CV upload/tailoring and profile "
        "import happen in the app's own UI, not through these tools."
    ),
)


@mcp_server.tool()
def search_jobs(keywords: str = "", location: str = "") -> dict:
    """Search and rank job listings against the user's profile. Merges Adzuna,
    Apollo, Apify (Google Jobs/Naukri/Indeed India/LinkedIn Jobs), and any
    manually-added listings -- same sources and ranking as the Job Search tab."""
    from app.routes import jobs as jobs_route

    result = jobs_route.search_jobs(criteria_id=None, what=keywords, where=location)
    return result.model_dump()


@mcp_server.tool()
def list_search_criteria() -> list[dict]:
    """List the user's saved search criteria sets (label, keywords, target roles,
    industries, locations)."""
    from app.routes import criteria as criteria_route

    return [c.model_dump() for c in criteria_route.list_criteria()]


@mcp_server.tool()
def get_profile_summary() -> dict:
    """Return the user's parsed LinkedIn profile summary: basics, skills,
    experience, education, certifications, and projects."""
    with db.get_db() as conn:
        return linkedin_export.load_profile_summary(conn)


@mcp_server.tool()
def get_salary_estimate(role: str, location: str = "") -> dict:
    """Estimate CTC/in-hand salary for a role and location from Adzuna's
    aggregate India salary data, adjusted for the user's inferred experience
    level. Same computation as the Salary Insights tab's Estimate action."""
    from app.routes import salary as salary_route

    result = salary_route.get_estimate(what=role, where=location)
    return result.model_dump()


@mcp_server.tool()
def list_manual_listings() -> list[dict]:
    """List job listings the user has added manually (pasted from Naukri,
    Indeed, LinkedIn, a careers page, etc.)."""
    with db.get_db() as conn:
        rows = conn.execute("SELECT * FROM manual_listings ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]
