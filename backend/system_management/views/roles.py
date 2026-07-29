from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.db.models import Count
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from operations.responses import bad_request, get_object_or_error, serializer_bad_request

from ..serializers import PermissionSerializer, RoleOptionSerializer, RoleSerializer, SystemUserSerializer
from ..services import UI_PERMISSION_CODES, ensure_feature_permissions, is_builtin_admin_user, record_operation_log
from .common import require_system_actions, require_system_permission, required_role_update_actions


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

    role, error = get_object_or_error(Group, id=role_id, error_message="角色不存在")
    if error:
        return error

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
    role, error = get_object_or_error(Group, id=role_id, error_message="角色不存在")
    if error:
        return error

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
