from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app import adzuna_client, apify_client, apollo_client, config

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
