import sqlite3

from app import config, linkedin_mcp_client

NAME = "linkedin_account"


def fetch(conn: sqlite3.Connection, criteria: dict) -> tuple[list[dict], list[str]]:
    """Optional, off-by-default source (Settings tab -> LinkedIn Account) that
    searches LinkedIn job listings via eliasbiondo/linkedin-mcp-server -- see
    app/linkedin_mcp_client.py for exactly what this does and why it's kept
    separate from every other source. Silently no-ops when disabled (same as
    when no keyword is given), rather than nagging users who haven't opted
    into this higher-risk feature."""
    if not config.LINKEDIN_MCP_ENABLED:
        return [], []

    keyword = " ".join(
        filter(None, [criteria.get("keywords", ""), criteria.get("target_roles", "")])
    ).strip()
    location = (criteria.get("locations") or "").strip()

    if not keyword:
        return [], []

    try:
        return linkedin_mcp_client.search_jobs(keyword, location), []
    except linkedin_mcp_client.LinkedInMcpError as exc:
        return [], [f"LinkedIn account search failed: {exc}"]
