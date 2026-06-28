from __future__ import annotations

import os

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.http import HttpRequest

from .models import LoginLog, SystemSetting

BUILTIN_ADMIN_USERNAME = "admin"
BUILTIN_ADMIN_EMAIL = "admin@ops.local"
BUILTIN_ADMIN_FIRST_NAME = "System Administrator"
BUILTIN_ADMIN_PASSWORD_ENV = "OPS_TOOL_ADMIN_PASSWORD"
BUILTIN_ADMIN_DEFAULT_PASSWORD = "Admin@123456"

FEATURE_PERMISSION_DEFINITIONS = [
    ("network", "网络工具", "ip", "IP 探活"),
    ("network", "网络工具", "ports", "机器探测"),
    ("network", "网络工具", "subnet", "IPv4 子网划分"),
    ("host", "主机管理", "hosts", "主机管理"),
    ("host", "主机管理", "accounts", "账号管理"),
    ("security", "安全工具", "auth", "双因子认证"),
    ("security", "安全工具", "password", "密码生成器"),
    ("security", "安全工具", "commandRules", "命令管理"),
    ("system", "系统管理", "loginLogs", "登录日志"),
    ("system", "系统管理", "users", "用户管理"),
    ("system", "系统管理", "roles", "角色管理"),
    ("system", "系统管理", "systemSettings", "系统设置"),
]

FEATURE_PERMISSION_CODE_BY_KEY = {key: f"access_{key}" for _, _, key, _ in FEATURE_PERMISSION_DEFINITIONS}
FEATURE_PERMISSION_CODES = set(FEATURE_PERMISSION_CODE_BY_KEY.values())
_feature_permissions_ready = False


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


def ensure_feature_permissions():
    global _feature_permissions_ready
    content_type = ContentType.objects.get_for_model(SystemSetting)
    if _feature_permissions_ready:
        cached_permissions = list(Permission.objects.filter(content_type=content_type, codename__in=FEATURE_PERMISSION_CODES))
        if len(cached_permissions) == len(FEATURE_PERMISSION_CODES):
            return cached_permissions

    permissions = []
    for _group_key, _group_label, feature_key, feature_label in FEATURE_PERMISSION_DEFINITIONS:
        permission, _created = Permission.objects.get_or_create(
            content_type=content_type,
            codename=FEATURE_PERMISSION_CODE_BY_KEY[feature_key],
            defaults={"name": f"访问{feature_label}"},
        )
        expected_name = f"访问{feature_label}"
        if permission.name != expected_name:
            permission.name = expected_name
            permission.save(update_fields=["name"])
        permissions.append(permission)
    _feature_permissions_ready = True
    return permissions


def user_feature_permission_codes(user) -> list[str]:
    if not user or not getattr(user, "is_authenticated", False):
        return []
    if getattr(user, "is_superuser", False):
        return sorted(FEATURE_PERMISSION_CODES)

    ensure_feature_permissions()
    codes = user.get_all_permissions()
    return sorted(code.split(".", 1)[1] for code in codes if code.split(".", 1)[-1] in FEATURE_PERMISSION_CODES)


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
