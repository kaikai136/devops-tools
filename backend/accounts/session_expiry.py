from __future__ import annotations

from django.contrib.auth import logout
from django.utils import timezone

from system_management.services import get_auth_session_settings

AUTH_SESSION_EXPIRES_AT_KEY = "ops_auth_expires_at"
AUTH_SESSION_STARTED_AT_KEY = "ops_auth_started_at"


def configured_session_expiry_seconds() -> int:
    minutes = int(get_auth_session_settings()["loginExpiryMinutes"])
    return minutes * 60


def apply_configured_session_expiry(request) -> None:
    seconds = configured_session_expiry_seconds()
    now = timezone.now().timestamp()
    expires_at = now + seconds
    request.session[AUTH_SESSION_STARTED_AT_KEY] = now
    request.session[AUTH_SESSION_EXPIRES_AT_KEY] = expires_at
    request.session.set_expiry(seconds)
    request.session.modified = True


def is_authenticated_session_expired(session) -> bool:
    now = timezone.now().timestamp()
    started_at = session.get(AUTH_SESSION_STARTED_AT_KEY)
    if started_at is not None:
        try:
            started_ts = float(started_at)
        except (TypeError, ValueError):
            return True
        if now >= started_ts + configured_session_expiry_seconds():
            return True
    expires_at = session.get(AUTH_SESSION_EXPIRES_AT_KEY)
    if expires_at is None:
        return False
    try:
        return float(expires_at) <= now
    except (TypeError, ValueError):
        return True


def logout_if_session_expired(request) -> bool:
    if is_authenticated_session_expired(request.session):
        logout(request)
        return True
    return False
