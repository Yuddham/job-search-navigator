import threading
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app import adzuna_client, apify_client, apollo_client, config, linkedin_mcp_client

router = APIRouter(prefix="/api/settings", tags=["settings"])


class KeysOut(BaseModel):
    adzuna_app_id: str
    adzuna_app_key: str
    apollo_api_key: str
    apify_api_token: str


class KeysIn(BaseModel):
    adzuna_app_id: Optional[str] = None
    adzuna_app_key: Optional[str] = None
    apollo_api_key: Optional[str] = None
    apify_api_token: Optional[str] = None


class ConnectionStatus(BaseModel):
    configured: bool
    connected: bool
    message: str


class StatusOut(BaseModel):
    adzuna: ConnectionStatus
    apollo: ConnectionStatus
    apify: ConnectionStatus


def _current_keys() -> KeysOut:
    return KeysOut(
        adzuna_app_id=config.ADZUNA_APP_ID,
        adzuna_app_key=config.ADZUNA_APP_KEY,
        apollo_api_key=config.APOLLO_API_KEY,
        apify_api_token=config.APIFY_API_TOKEN,
    )


@router.get("/keys", response_model=KeysOut)
def get_keys() -> KeysOut:
    return _current_keys()


@router.put("/keys", response_model=KeysOut)
def update_keys(payload: KeysIn) -> KeysOut:
    field_to_env = {
        "adzuna_app_id": "ADZUNA_APP_ID",
        "adzuna_app_key": "ADZUNA_APP_KEY",
        "apollo_api_key": "APOLLO_API_KEY",
        "apify_api_token": "APIFY_API_TOKEN",
    }
    updates = {}
    for field, env_key in field_to_env.items():
        value = getattr(payload, field)
        if value is not None:
            updates[env_key] = value.strip()

    config.update_env_values(updates)

    # A swapped-out key invalidates anything cached under the old credentials
    # (the caches are keyed by request params, not by credential, so a stale
    # success/failure could otherwise linger under the new key).
    adzuna_client.clear_cache()
    apollo_client.clear_cache()
    apify_client.clear_cache()

    return _current_keys()


def _check_adzuna() -> ConnectionStatus:
    if not config.ADZUNA_APP_ID or not config.ADZUNA_APP_KEY:
        return ConnectionStatus(configured=False, connected=False, message="Not configured")
    try:
        adzuna_client.search_jobs(what="test", where="", results_per_page=1)
        return ConnectionStatus(configured=True, connected=True, message="Connected")
    except adzuna_client.AdzunaAPIError as exc:
        return ConnectionStatus(configured=True, connected=False, message=str(exc))
    except Exception as exc:  # defensive -- a status check should never 500 the tab
        return ConnectionStatus(configured=True, connected=False, message=f"Unexpected error: {exc}")


def _check_apollo() -> ConnectionStatus:
    if not config.APOLLO_API_KEY:
        return ConnectionStatus(configured=False, connected=False, message="Not configured")
    try:
        apollo_client.search_companies(keyword="test", per_page=1)
        return ConnectionStatus(configured=True, connected=True, message="Connected")
    except apollo_client.ApolloAPIError as exc:
        return ConnectionStatus(configured=True, connected=False, message=str(exc))
    except Exception as exc:
        return ConnectionStatus(configured=True, connected=False, message=f"Unexpected error: {exc}")


def _check_apify() -> ConnectionStatus:
    if not config.APIFY_API_TOKEN:
        return ConnectionStatus(configured=False, connected=False, message="Not configured")
    try:
        apify_client.validate_token()
        return ConnectionStatus(configured=True, connected=True, message="Connected")
    except apify_client.ApifyAPIError as exc:
        return ConnectionStatus(configured=True, connected=False, message=str(exc))
    except Exception as exc:
        return ConnectionStatus(configured=True, connected=False, message=f"Unexpected error: {exc}")


@router.get("/status", response_model=StatusOut)
def get_status() -> StatusOut:
    return StatusOut(adzuna=_check_adzuna(), apollo=_check_apollo(), apify=_check_apify())


class AppKeyOut(BaseModel):
    app_key: str
    mcp_url: str


def _app_key_out(request: Request) -> AppKeyOut:
    # Trailing slash is required: Starlette's Mount only dispatches "/mcp/..."
    # into the MCP app, not the bare "/mcp" (that 404s before auth even runs).
    return AppKeyOut(app_key=config.APP_KEY, mcp_url=str(request.base_url).rstrip("/") + "/mcp/")


@router.get("/app-key", response_model=AppKeyOut)
def get_app_key(request: Request) -> AppKeyOut:
    """This is NOT one of the Adzuna/Apollo/Apify credentials -- it's a key
    this app generates itself, so external tools (Claude Code, other MCP
    clients) can authenticate into this app's own /mcp endpoint."""
    return _app_key_out(request)


@router.post("/app-key/regenerate", response_model=AppKeyOut)
def regenerate_app_key_route(request: Request) -> AppKeyOut:
    config.regenerate_app_key()
    return _app_key_out(request)


class LinkedInAccountStatus(BaseModel):
    tooling_available: bool
    installed: bool
    connected: bool
    enabled: bool
    connecting: bool
    error: Optional[str] = None


class LinkedInEnableIn(BaseModel):
    enabled: bool


_linkedin_connect_state: dict = {"connecting": False, "error": None}


@router.get("/linkedin-account", response_model=LinkedInAccountStatus)
def get_linkedin_account_status() -> LinkedInAccountStatus:
    """Status for the Settings tab's LinkedIn Account section -- see
    app/linkedin_mcp_client.py for what this feature is and why it's kept
    separate from the Adzuna/Apollo/Apify keys above."""
    s = linkedin_mcp_client.status()
    return LinkedInAccountStatus(
        **s,
        connecting=_linkedin_connect_state["connecting"],
        error=_linkedin_connect_state["error"],
    )


@router.post("/linkedin-account/enable", response_model=LinkedInAccountStatus)
def set_linkedin_account_enabled(payload: LinkedInEnableIn) -> LinkedInAccountStatus:
    config.update_env_values({"LINKEDIN_MCP_ENABLED": "true" if payload.enabled else "false"})
    return get_linkedin_account_status()


def _connect_in_background() -> None:
    try:
        linkedin_mcp_client.start_login()
    except Exception as exc:  # noqa: BLE001 -- surfaced to the UI via status polling
        _linkedin_connect_state["error"] = str(exc)
    finally:
        _linkedin_connect_state["connecting"] = False


@router.post("/linkedin-account/connect", response_model=LinkedInAccountStatus)
def connect_linkedin_account() -> LinkedInAccountStatus:
    """Kicks off install (if needed) + the interactive --login flow in the
    background and returns immediately -- installing alone can take minutes
    (git clone + a Patchright browser download), and login itself opens a
    real browser window for the user to sign into LinkedIn themselves, which
    this endpoint can't wait on. The frontend polls GET .../linkedin-account
    afterward to see when it's installed/connected."""
    if not _linkedin_connect_state["connecting"]:
        _linkedin_connect_state["connecting"] = True
        _linkedin_connect_state["error"] = None
        threading.Thread(target=_connect_in_background, daemon=True).start()
    return get_linkedin_account_status()
