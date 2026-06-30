from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.db.models import CharField
from django.db.models.functions import Cast
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from accounts.models import UserProfile
from accounts.permissions import has_feature_permission, require_feature_permission, require_login
from operations.responses import bad_request, bounded_int, not_found, serializer_bad_request

from .dashboard import build_dashboard_summary
from .models import LoginLog, SystemSetting
from .serializers import WATERMARK_SETTING_KEY, LoginLogSerializer, PermissionSerializer, RoleSerializer, SystemSettingSerializer, SystemUserSerializer
from .services import UI_PERMISSION_CODES, ensure_builtin_admin, ensure_feature_permissions, is_builtin_admin_user


SYSTEM_PERMISSION_MESSAGES = {
    "dashboard": "没有仪表盘访问权限",
    "loginLogs": "没有登录日志权限",
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


@api_view(["GET"])
def dashboard_summary(request):
    access_error = require_dashboard_access(request)
    if access_error:
        return access_error
    return Response(build_dashboard_summary())


@api_view(["GET"])
def login_logs(request):
    access_error = require_system_permission(request, "loginLogs")
    if access_error:
        return access_error

    queryset = LoginLog.objects.select_related("user")
    status_filter = str(request.query_params.get("status", "")).strip()
    username = str(request.query_params.get("username", "")).strip()
    ip_address = str(request.query_params.get("ip", request.query_params.get("ipAddress", ""))).strip()
    if status_filter in {LoginLog.STATUS_SUCCESS, LoginLog.STATUS_FAILED}:
        queryset = queryset.filter(status=status_filter)
    if username:
        queryset = queryset.filter(username__icontains=username)
    if ip_address:
        queryset = queryset.annotate(ip_address_text=Cast("ip_address", CharField())).filter(ip_address_text__icontains=ip_address)

    page = bounded_int(request.query_params.get("page", 1), default=1, minimum=1, maximum=100000)
    page_size = bounded_int(
        request.query_params.get("pageSize", request.query_params.get("limit", 10)),
        default=10,
        minimum=1,
        maximum=100,
    )
    total = queryset.count()
    start = (page - 1) * page_size
    end = start + page_size
    return Response(
        {
            "results": LoginLogSerializer(queryset[start:end], many=True).data,
            "total": total,
            "page": page,
            "pageSize": page_size,
        }
    )


@api_view(["GET", "POST"])
def system_users(request):
    access_error = require_system_permission(request, "users", "create" if request.method == "POST" else None)
    if access_error:
        return access_error

    User = get_user_model()
    ensure_builtin_admin()
    if request.method == "GET":
        users = User.objects.prefetch_related("groups").order_by("id")
        return Response(SystemUserSerializer(users, many=True).data)

    serializer = SystemUserSerializer(data=request.data)
    if not serializer.is_valid():
        return serializer_bad_request(serializer)
    user = serializer.save()
    return Response(SystemUserSerializer(user).data, status=status.HTTP_201_CREATED)


@api_view(["GET", "PUT", "DELETE"])
def system_user_detail(request, user_id: int):
    access_error = require_system_permission(request, "users")
    if access_error:
        return access_error

    User = get_user_model()
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return not_found("用户不存在")

    if request.method == "GET":
        return Response(SystemUserSerializer(user).data)

    if request.method == "DELETE":
        action_error = require_system_permission(request, "users", "delete")
        if action_error:
            return action_error
        if user.id == request.user.id:
            return bad_request("不能删除当前登录用户")
        if is_builtin_admin_user(user):
            return bad_request("内置管理员不允许删除")
        user.delete()
        return Response({"deleted": True})

    action_error = require_system_actions(request, "users", required_user_update_actions(request, user))
    if action_error:
        return action_error

    serializer = SystemUserSerializer(user, data=request.data, partial=True)
    if not serializer.is_valid():
        return serializer_bad_request(serializer)
    saved_user = serializer.save()
    if is_builtin_admin_user(saved_user):
        saved_user = ensure_builtin_admin()
    return Response(SystemUserSerializer(saved_user).data)


def _get_manageable_2fa_user(request, user_id: int):
    User = get_user_model()
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return None, not_found("用户不存在")
    if user.id == request.user.id:
        return None, bad_request("不能在用户列表中操作当前登录用户的 2FA")
    if is_builtin_admin_user(user):
        return None, bad_request("内置管理员不允许在用户列表中操作 2FA")
    return user, None


@api_view(["POST"])
def system_user_2fa_enable(request, user_id: int):
    access_error = require_system_permission(request, "users", "2fa_enable")
    if access_error:
        return access_error

    user, error = _get_manageable_2fa_user(request, user_id)
    if error:
        return error

    profile, _created = UserProfile.objects.get_or_create(user=user)
    profile.totp_pending_secret = ""
    profile.totp_reset_required = False
    if profile.totp_secret:
        profile.totp_enabled = True
        profile.totp_required = False
        update_fields = ["totp_pending_secret", "totp_enabled", "totp_required", "totp_reset_required", "updated_at"]
    else:
        profile.totp_enabled = False
        profile.totp_required = True
        profile.totp_confirmed_at = None
        update_fields = ["totp_pending_secret", "totp_enabled", "totp_required", "totp_reset_required", "totp_confirmed_at", "updated_at"]
    profile.save(
        update_fields=update_fields
    )
    return Response(SystemUserSerializer(user).data)


@api_view(["POST"])
def system_user_2fa_disable(request, user_id: int):
    access_error = require_system_permission(request, "users", "2fa_disable")
    if access_error:
        return access_error

    user, error = _get_manageable_2fa_user(request, user_id)
    if error:
        return error

    profile, _created = UserProfile.objects.get_or_create(user=user)
    profile.totp_pending_secret = ""
    profile.totp_enabled = False
    profile.totp_required = False
    profile.totp_reset_required = False
    profile.save(
        update_fields=[
            "totp_pending_secret",
            "totp_enabled",
            "totp_required",
            "totp_reset_required",
            "updated_at",
        ]
    )
    return Response(SystemUserSerializer(user).data)


@api_view(["POST"])
def system_user_2fa_reset(request, user_id: int):
    access_error = require_system_permission(request, "users", "2fa_reset")
    if access_error:
        return access_error

    user, error = _get_manageable_2fa_user(request, user_id)
    if error:
        return error

    profile, _created = UserProfile.objects.get_or_create(user=user)
    profile.totp_secret = ""
    profile.totp_pending_secret = ""
    profile.totp_enabled = False
    profile.totp_required = True
    profile.totp_reset_required = False
    profile.totp_confirmed_at = None
    profile.save(
        update_fields=[
            "totp_secret",
            "totp_pending_secret",
            "totp_enabled",
            "totp_required",
            "totp_reset_required",
            "totp_confirmed_at",
            "updated_at",
        ]
    )
    return Response(SystemUserSerializer(user).data)


@api_view(["GET", "POST"])
def roles(request):
    access_error = require_system_permission(request, "roles", "create" if request.method == "POST" else None)
    if access_error:
        return access_error

    if request.method == "GET":
        ensure_feature_permissions()
        return Response(RoleSerializer(Group.objects.prefetch_related("permissions").order_by("id"), many=True).data)

    serializer = RoleSerializer(data=request.data)
    if not serializer.is_valid():
        return serializer_bad_request(serializer)
    return Response(RoleSerializer(serializer.save()).data, status=status.HTTP_201_CREATED)


@api_view(["GET", "PUT", "DELETE"])
def role_detail(request, role_id: int):
    access_error = require_system_permission(request, "roles")
    if access_error:
        return access_error

    try:
        role = Group.objects.get(id=role_id)
    except Group.DoesNotExist:
        return not_found("角色不存在")

    if request.method == "GET":
        return Response(RoleSerializer(role).data)

    if request.method == "DELETE":
        action_error = require_system_permission(request, "roles", "delete")
        if action_error:
            return action_error
        role.delete()
        return Response({"deleted": True})

    action_error = require_system_actions(request, "roles", required_role_update_actions(request, role))
    if action_error:
        return action_error

    serializer = RoleSerializer(role, data=request.data, partial=True)
    if not serializer.is_valid():
        return serializer_bad_request(serializer)
    return Response(RoleSerializer(serializer.save()).data)


@api_view(["GET"])
def permissions(request):
    access_error = require_system_permission(request, "roles")
    if access_error:
        return access_error

    ensure_feature_permissions()
    queryset = Permission.objects.select_related("content_type").filter(codename__in=UI_PERMISSION_CODES).order_by("id")
    return Response(PermissionSerializer(queryset, many=True).data)


@api_view(["GET", "POST"])
def system_settings(request):
    access_error = require_system_permission(request, "systemSettings", "save" if request.method == "POST" else None)
    if access_error:
        return access_error

    if request.method == "GET":
        return Response(SystemSettingSerializer(SystemSetting.objects.all(), many=True).data)

    serializer = SystemSettingSerializer(data=request.data)
    if not serializer.is_valid():
        return serializer_bad_request(serializer)
    return Response(SystemSettingSerializer(serializer.save()).data, status=status.HTTP_201_CREATED)


@api_view(["GET", "PUT", "DELETE"])
def system_setting_detail(request, setting_key: str):
    if request.method == "GET" and setting_key == WATERMARK_SETTING_KEY:
        auth_error = require_login(request)
        if auth_error:
            return auth_error
    else:
        action_key = "save" if request.method in {"PUT", "DELETE"} else None
        access_error = require_system_permission(request, "systemSettings", action_key)
        if access_error:
            return access_error

    try:
        setting = SystemSetting.objects.get(key=setting_key)
    except SystemSetting.DoesNotExist:
        return not_found("系统设置不存在")

    if request.method == "GET":
        return Response(SystemSettingSerializer(setting).data)

    if request.method == "DELETE":
        setting.delete()
        return Response({"deleted": True})

    serializer = SystemSettingSerializer(setting, data=request.data, partial=True)
    if not serializer.is_valid():
        return serializer_bad_request(serializer)
    return Response(SystemSettingSerializer(serializer.save()).data)
