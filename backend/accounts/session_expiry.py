from __future__ import annotations

from django.contrib.auth import logout
from django.utils import timezone

from system_management.services import get_auth_session_settings

AUTH_SESSION_EXPIRES_AT_KEY = "ops_auth_expires_at"


def configured_session_expiry_seconds() -> int:
    minutes = int(get_auth_session_settings()["loginExpiryMinutes"])
    return minutes * 60


def apply_configured_session_expiry(request) -> None:
    seconds = configured_session_expiry_seconds()
    expires_at = timezone.now().timestamp() + seconds
    request.session[AUTH_SESSION_EXPIRES_AT_KEY] = expires_at
    request.session.set_expiry(seconds)
    request.session.modified = True


def is_authenticated_session_expired(session) -> bool:
    expires_at = session.get(AUTH_SESSION_EXPIRES_AT_KEY)
    if expires_at is None:
        return False
    try:
        return float(expires_at) <= timezone.now().timestamp()
    except (TypeError, ValueError):
        return True


def logout_if_session_expired(request) -> bool:
    if is_authenticated_session_expired(request.session):
        logout(request)
        return True
    return False
