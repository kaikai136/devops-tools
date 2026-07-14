from datetime import datetime, time
from functools import wraps

from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from accounts.permissions import require_feature_permission, require_login


def terminal_login_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        auth_error = require_login(request)
        if auth_error:
            return auth_error
        return view_func(request, *args, **kwargs)

    return wrapped


def quick_command_permission_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        permission_error = require_feature_permission(request, "hosts", "quick_commands", "没有快捷命令权限")
        if permission_error:
            return permission_error
        return view_func(request, *args, **kwargs)

    return wrapped


def session_audit_permission_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        permission_error = require_feature_permission(request, "hosts", "session_audit", "没有会话审计权限")
        if permission_error:
            return permission_error
        return view_func(request, *args, **kwargs)

    return wrapped


def parse_positive_int(value, default: int, minimum: int = 1, maximum: int = 100) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(parsed, maximum))


def parse_audit_datetime(value: str, end_of_day: bool = False):
    raw = str(value or "").strip()
    if not raw:
        return None
    parsed = parse_datetime(raw)
    if parsed is None:
        parsed_date = parse_date(raw)
        if parsed_date is None:
            return None
        parsed = datetime.combine(parsed_date, time.max if end_of_day else time.min)
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed)
    return parsed
