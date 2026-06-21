from __future__ import annotations

from django.http import HttpRequest

from .models import LoginLog


def get_client_ip(request: HttpRequest) -> str | None:
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None


def record_login_log(request: HttpRequest, username: str, status: str, message: str = "", user=None) -> LoginLog:
    return LoginLog.objects.create(
        user=user if getattr(user, "is_authenticated", False) else None,
        username=username,
        ip_address=get_client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
        status=status,
        message=message,
    )
