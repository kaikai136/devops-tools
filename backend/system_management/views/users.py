from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from accounts.models import UserProfile
from operations.responses import bad_request, get_object_or_error, serializer_bad_request

from ..serializers import SystemUserSerializer
from ..services import ensure_builtin_admin, is_builtin_admin_user, record_operation_log
from .common import (
    _coerce_bool,
    require_system_actions,
    require_system_permission,
    required_user_update_actions,
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
    user, error = get_object_or_error(User, id=user_id, error_message="用户不存在")
    if error:
        return error

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
    user, error = get_object_or_error(User, id=user_id, error_message="用户不存在")
    if error:
        return None, error
    if user.id == request.user.id:
        return None, bad_request("不能在用户列表中操作当前登录用户的 2FA")
    if is_builtin_admin_user(user):
        return None, bad_request("内置管理员不允许在用户列表中操作 2FA")
    return user, None


def _get_manageable_session_audit_user(request, user_id: int):
    User = get_user_model()
    user, error = get_object_or_error(User, id=user_id, error_message="用户不存在")
    if error:
        return None, error
    if user.id == request.user.id and not is_builtin_admin_user(user):
        return None, bad_request("不能在用户列表中操作当前登录用户的会话审计")
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
