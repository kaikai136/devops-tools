from rest_framework import status
from rest_framework.response import Response

from accounts.permissions import has_feature_permission, require_feature_permission

SYSTEM_PERMISSION_MESSAGES = {
    "dashboard": "没有仪表盘访问权限",
    "loginLogs": "没有登录日志权限",
    "operationLogs": "没有操作日志权限",
    "users": "没有用户管理权限",
    "roles": "没有角色管理权限",
    "systemSettings": "没有系统设置权限",
}


def require_dashboard_access(request):
    return require_system_permission(request, "dashboard")


def require_system_permission(request, feature_key: str, action_key: str | None = None):
    return require_feature_permission(
        request,
        feature_key,
        action_key,
        SYSTEM_PERMISSION_MESSAGES.get(feature_key, "没有操作权限"),
    )


def require_system_actions(request, feature_key: str, action_keys):
    access_error = require_system_permission(request, feature_key)
    if access_error:
        return access_error

    required_actions = {action_key for action_key in action_keys if action_key}
    for action_key in required_actions:
        if not has_feature_permission(request.user, feature_key, action_key):
            return Response({"error": SYSTEM_PERMISSION_MESSAGES.get(feature_key, "没有操作权限")}, status=status.HTTP_403_FORBIDDEN)
    return None


def _coerce_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _request_role_ids(data):
    if "roleIds" not in data:
        return None

    raw_role_ids = data.get("roleIds", [])
    if isinstance(raw_role_ids, str):
        values = [raw_role_ids] if raw_role_ids.strip() else []
    else:
        values = list(raw_role_ids)

    try:
        return sorted(int(value) for value in values)
    except (TypeError, ValueError):
        return None


def required_user_update_actions(request, user):
    data = request.data
    actions = set()
    password = str(data.get("password", "")).strip()
    if password:
        actions.add("reset_password")

    if "isActive" in data and _coerce_bool(data.get("isActive")) != user.is_active:
        actions.add("toggle_status")

    editable_fields = [
        ("username", user.username),
        ("email", user.email),
        ("firstName", user.first_name),
        ("isStaff", user.is_staff),
    ]
    for key, current_value in editable_fields:
        if key not in data:
            continue
        next_value = _coerce_bool(data.get(key)) if isinstance(current_value, bool) else str(data.get(key, "")).strip()
        if next_value != current_value:
            actions.add("edit")

    next_role_ids = _request_role_ids(data)
    if next_role_ids is not None:
        current_role_ids = sorted(user.groups.values_list("id", flat=True))
        if next_role_ids != current_role_ids:
            actions.add("edit")

    if not actions:
        actions.add("edit")
    return actions


def required_role_update_actions(request, role):
    actions = set()
    name = str(request.data.get("name", role.name)).strip()
    if name != role.name:
        actions.add("edit")

    if "permissionIds" in request.data:
        raw_permission_ids = request.data.get("permissionIds", [])
        if isinstance(raw_permission_ids, str):
            values = [raw_permission_ids] if raw_permission_ids.strip() else []
        else:
            values = list(raw_permission_ids)
        try:
            next_permission_ids = sorted(int(value) for value in values)
        except (TypeError, ValueError):
            next_permission_ids = []
        current_permission_ids = sorted(role.permissions.values_list("id", flat=True))
        if next_permission_ids != current_permission_ids:
            actions.add("permissions")

    if not actions:
        actions.add("edit")
    return actions
