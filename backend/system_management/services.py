from __future__ import annotations

import os

from django.contrib.auth import get_user_model
from django.http import HttpRequest

from .models import LoginLog

BUILTIN_ADMIN_USERNAME = "admin"
BUILTIN_ADMIN_EMAIL = "admin@ops.local"
BUILTIN_ADMIN_FIRST_NAME = "System Administrator"
BUILTIN_ADMIN_PASSWORD_ENV = "OPS_TOOL_ADMIN_PASSWORD"
BUILTIN_ADMIN_DEFAULT_PASSWORD = "Admin@123456"


def is_builtin_admin_user(user) -> bool:
    return bool(user and getattr(user, "username", "") == BUILTIN_ADMIN_USERNAME)


def ensure_builtin_admin():
    User = get_user_model()
    user, created = User.objects.get_or_create(
        username=BUILTIN_ADMIN_USERNAME,
        defaults={
            "email": BUILTIN_ADMIN_EMAIL,
            "first_name": BUILTIN_ADMIN_FIRST_NAME,
            "is_active": True,
            "is_staff": True,
            "is_superuser": True,
        },
    )

    update_fields: list[str] = []
    fixed_fields = {
        "email": BUILTIN_ADMIN_EMAIL,
        "first_name": BUILTIN_ADMIN_FIRST_NAME,
        "is_active": True,
        "is_staff": True,
        "is_superuser": True,
    }
    for field, value in fixed_fields.items():
        if getattr(user, field) != value:
            setattr(user, field, value)
            update_fields.append(field)

    admin_password = os.environ.get(BUILTIN_ADMIN_PASSWORD_ENV, "").strip() or BUILTIN_ADMIN_DEFAULT_PASSWORD
    if not user.check_password(admin_password):
        user.set_password(admin_password)
        update_fields.append("password")

    if update_fields:
        user.save(update_fields=list(dict.fromkeys(update_fields)))
    return user


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
