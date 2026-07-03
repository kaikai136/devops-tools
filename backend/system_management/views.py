from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.db.models import CharField, Count, Q
from django.db.models.functions import Cast
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from accounts.models import UserProfile
from accounts.permissions import has_feature_permission, require_feature_permission, require_login
from operations.responses import bad_request, bounded_int, not_found, serializer_bad_request

from .dashboard import build_dashboard_summary
from .models import LoginLog, OperationLog, SystemSetting
from .serializers import DISPLAY_SETTING_KEYS, PUBLIC_DISPLAY_SETTING_KEYS, LoginLogSerializer, OperationLogSerializer, PermissionSerializer, RoleOptionSerializer, RoleSerializer, SystemSettingSerializer, SystemUserSerializer
from .services import UI_PERMISSION_CODES, ensure_builtin_admin, ensure_feature_permissions, is_builtin_admin_user, record_operation_log


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


@api_view(["GET"])
def operation_logs(request):
    access_error = require_system_permission(request, "operationLogs")
    if access_error:
        return access_error

    queryset = OperationLog.objects.select_related("user")
    username = str(request.query_params.get("username", "")).strip()
    module = str(request.query_params.get("module", "")).strip()
    action = str(request.query_params.get("action", "")).strip()
    keyword = str(request.query_params.get("keyword", "")).strip()
    ip_address = str(request.query_params.get("ip", request.query_params.get("ipAddress", ""))).strip()

    if username:
        queryset = queryset.filter(username__icontains=username)
    if module:
        queryset = queryset.filter(module__icontains=module)
    if action:
        queryset = queryset.filter(action__icontains=action)
    if keyword:
        queryset = queryset.filter(
            Q(target__icontains=keyword)
            | Q(detail__icontains=keyword)
            | Q(module__icontains=keyword)
            | Q(action__icontains=keyword)
            | Q(username__icontains=keyword)
        )
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
            "results": OperationLogSerializer(queryset[start:end], many=True).data,
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
        users = User.objects.select_related("profile").prefetch_related("groups").order_by("id")
        return Response(SystemUserSerializer(users, many=True).data)

    serializer = SystemUserSerializer(data=request.data)
    if not serializer.is_valid():
        return serializer_bad_request(serializer)
    user = serializer.save()
    record_operation_log(request, "用户管理", "新建用户", user.username, f"用户ID: {user.id}")
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
        target = user.username
        user_id = user.id
        user.delete()
        record_operation_log(request, "用户管理", "删除用户", target, f"用户ID: {user_id}")
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
    record_operation_log(request, "用户管理", "编辑用户", saved_user.username, f"用户ID: {saved_user.id}")
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


def _get_manageable_session_audit_user(request, user_id: int):
    User = get_user_model()
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return None, not_found("用户不存在")
    if user.id == request.user.id:
        return None, bad_request("不能在用户列表中操作当前登录用户的会话审计")
    if is_builtin_admin_user(user):
        return None, bad_request("内置管理员不允许在用户列表中操作会话审计")
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
    record_operation_log(request, "用户管理", "开启 2FA", user.username, f"用户ID: {user.id}")
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
    record_operation_log(request, "用户管理", "关闭 2FA", user.username, f"用户ID: {user.id}")
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
    record_operation_log(request, "用户管理", "重置 2FA", user.username, f"用户ID: {user.id}")
    return Response(SystemUserSerializer(user).data)


@api_view(["POST"])
def system_user_session_audit(request, user_id: int):
    access_error = require_system_permission(request, "users", "session_audit")
    if access_error:
        return access_error

    user, error = _get_manageable_session_audit_user(request, user_id)
    if error:
        return error

    profile, _created = UserProfile.objects.get_or_create(user=user)
    enabled = _coerce_bool(request.data.get("enabled")) if "enabled" in request.data else not profile.session_audit_enabled
    profile.session_audit_enabled = enabled
    profile.save(update_fields=["session_audit_enabled", "updated_at"])

    action = "开启会话审计" if enabled else "关闭会话审计"
    record_operation_log(request, "用户管理", action, user.username, f"用户ID: {user.id}")
    return Response(SystemUserSerializer(user).data)


@api_view(["GET", "POST"])
def roles(request):
    access_error = require_system_permission(request, "roles", "create" if request.method == "POST" else None)
    if access_error:
        return access_error

    if request.method == "GET":
        ensure_feature_permissions()
        roles_queryset = Group.objects.annotate(user_count=Count("user")).prefetch_related("permissions").order_by("id")
        return Response(RoleSerializer(roles_queryset, many=True).data)

    serializer = RoleSerializer(data=request.data)
    if not serializer.is_valid():
        return serializer_bad_request(serializer)
    role = serializer.save()
    record_operation_log(request, "角色管理", "新增角色", role.name, f"角色ID: {role.id}")
    return Response(RoleSerializer(role).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
def role_options(request):
    access_error = require_system_permission(request, "users")
    if access_error:
        return access_error

    return Response(RoleOptionSerializer(Group.objects.order_by("id"), many=True).data)


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
        target = role.name
        role_id = role.id
        role.delete()
        record_operation_log(request, "角色管理", "删除角色", target, f"角色ID: {role_id}")
        return Response({"deleted": True})

    role_actions = required_role_update_actions(request, role)
    action_error = require_system_actions(request, "roles", role_actions)
    if action_error:
        return action_error

    serializer = RoleSerializer(role, data=request.data, partial=True)
    if not serializer.is_valid():
        return serializer_bad_request(serializer)
    saved_role = serializer.save()
    action_label = "调整权限" if "permissions" in role_actions and len(role_actions) == 1 else "编辑角色"
    record_operation_log(request, "角色管理", action_label, saved_role.name, f"角色ID: {saved_role.id}")
    return Response(RoleSerializer(saved_role).data)


@api_view(["GET", "PUT"])
def role_users(request, role_id: int):
    access_error = require_system_permission(request, "roles", "edit" if request.method == "PUT" else None)
    if access_error:
        return access_error

    User = get_user_model()
    try:
        role = Group.objects.get(id=role_id)
    except Group.DoesNotExist:
        return not_found("角色不存在")

    users = list(User.objects.select_related("profile").prefetch_related("groups").order_by("id"))
    if request.method == "GET":
        return Response({"role": RoleSerializer(role).data, "users": SystemUserSerializer(users, many=True).data})

    raw_user_ids = request.data.get("userIds", [])
    if isinstance(raw_user_ids, str):
        values = [raw_user_ids] if raw_user_ids.strip() else []
    else:
        values = list(raw_user_ids)
    try:
        selected_ids = {int(value) for value in values}
    except (TypeError, ValueError):
        return bad_request("用户数据不正确")

    users_by_id = {user.id: user for user in users}
    unknown_ids = selected_ids - set(users_by_id)
    if unknown_ids:
        return bad_request("用户不存在")

    builtin_ids = {user.id for user in users if is_builtin_admin_user(user)}
    if selected_ids & builtin_ids:
        return bad_request("内置管理员不允许调整角色")

    for user in users:
        if user.id in builtin_ids:
            continue
        if user.id in selected_ids:
            user.groups.set([role])
        elif user.groups.filter(id=role.id).exists():
            user.groups.remove(role)

    role = Group.objects.annotate(user_count=Count("user")).prefetch_related("permissions").get(id=role.id)
    users = User.objects.select_related("profile").prefetch_related("groups").order_by("id")
    selected_usernames = [users_by_id[user_id].username for user_id in sorted(selected_ids)]
    detail = f"绑定用户数: {len(selected_usernames)}"
    if selected_usernames:
        detail = f"{detail}; 用户: {', '.join(selected_usernames[:20])}"
        if len(selected_usernames) > 20:
            detail = f"{detail} 等"
    record_operation_log(request, "角色管理", "调整权限用户", role.name, detail)
    return Response({"role": RoleSerializer(role).data, "users": SystemUserSerializer(users, many=True).data})


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
    setting = serializer.save()
    record_operation_log(request, "系统设置", "新增设置", setting.key, setting.label or setting.description)
    return Response(SystemSettingSerializer(setting).data, status=status.HTTP_201_CREATED)


@api_view(["GET", "PUT", "DELETE"])
def system_setting_detail(request, setting_key: str):
    if request.method == "GET" and setting_key in PUBLIC_DISPLAY_SETTING_KEYS:
        pass
    elif request.method == "GET" and setting_key in DISPLAY_SETTING_KEYS:
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
        target = setting.key
        detail = setting.label or setting.description
        setting.delete()
        record_operation_log(request, "系统设置", "删除设置", target, detail)
        return Response({"deleted": True})

    serializer = SystemSettingSerializer(setting, data=request.data, partial=True)
    if not serializer.is_valid():
        return serializer_bad_request(serializer)
    saved_setting = serializer.save()
    record_operation_log(request, "系统设置", "保存设置", saved_setting.key, saved_setting.label or saved_setting.description)
    return Response(SystemSettingSerializer(saved_setting).data)
