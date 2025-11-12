import base64
from typing import Optional

from fastapi import Depends, HTTPException, Request, WebSocket, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBasic, HTTPBearer
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from ldap3 import Connection, Server

from app.config import Settings, get_settings

basic_scheme = HTTPBasic()
bearer_scheme = HTTPBearer(auto_error=False)


def _validate_active_directory_credentials(
    settings: Settings, username: str, password: str
) -> str:
    if not settings.ad_server_uri or not settings.ad_user_dn_template:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Active Directory is not fully configured.",
        )

    server = Server(settings.ad_server_uri, use_ssl=settings.ad_use_ssl, get_info=None)
    user_dn = settings.ad_user_dn_template.format(username=username)


    try:
        with Connection(server, user=user_dn, password=password, auto_bind=True):
            return username
    except Exception as exc:  # pragma: no cover - depends on external directory
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Active Directory credentials.",
        ) from exc


def _validate_google_token(settings: Settings, token: str) -> str:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Google token.",
        )

    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google authentication is not fully configured.",
        )

    try:
        info = id_token.verify_oauth2_token(
            token, google_requests.Request(), settings.google_client_id
        )
    except Exception as exc:  # pragma: no cover - external dependency failures
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google token.",
        ) from exc
    return info.get("email") or info.get("sub")


def get_current_principal(
    request: Request, settings: Settings = Depends(get_settings)
) -> Optional[str]:
    """Return the identity associated with the request or None when auth disabled."""

    if settings.auth_provider == "none":
        return None

    if settings.auth_provider == "active_directory":
        credentials = basic_scheme(request)
        decoded = base64.b64decode(credentials.credentials).decode("utf-8")
        username, _, password = decoded.partition(":")
        if not password:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credential payload.",
            )
        return _validate_active_directory_credentials(settings, username, password)

    if settings.auth_provider == "google":
        credentials = bearer_scheme(request)
        if not isinstance(credentials, HTTPAuthorizationCredentials):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Google credentials are required.",
            )
        return _validate_google_token(settings, credentials.credentials)

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Unsupported authentication provider configured.",
    )


def get_websocket_principal(
    websocket: WebSocket, settings: Settings = Depends(get_settings)
) -> Optional[str]:
    if settings.auth_provider == "none":
        return None

    token = websocket.query_params.get("token")

    if settings.auth_provider == "active_directory":
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Active Directory token missing.",
            )
        decoded = base64.b64decode(token).decode("utf-8")
        username, _, password = decoded.partition(":")
        if not password:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credential payload.",
            )
        return _validate_active_directory_credentials(settings, username, password)

    if settings.auth_provider == "google":
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Google token required for websocket connections.",
            )
        return _validate_google_token(settings, token)

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Unsupported authentication provider configured.",
    )
