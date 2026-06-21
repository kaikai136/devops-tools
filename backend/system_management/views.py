from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from accounts.views import require_staff
from operations.responses import bad_request

from .models import LoginLog, SystemSetting
from .serializers import LoginLogSerializer, PermissionSerializer, RoleSerializer, SystemSettingSerializer, SystemUserSerializer
from .services import ensure_builtin_admin, is_builtin_admin_user


@api_view(["GET"])
def login_logs(request):
    staff_error = require_staff(request)
    if staff_error:
        return staff_error

    queryset = LoginLog.objects.select_related("user")
    status_filter = str(request.query_params.get("status", "")).strip()
    username = str(request.query_params.get("username", "")).strip()
    if status_filter:
        queryset = queryset.filter(status=status_filter)
    if username:
        queryset = queryset.filter(username__icontains=username)

    limit = bounded_int(request.query_params.get("limit", 100), default=100, minimum=1, maximum=500)
    return Response(LoginLogSerializer(queryset[:limit], many=True).data)


@api_view(["GET", "POST"])
def system_users(request):
    staff_error = require_staff(request)
    if staff_error:
        return staff_error

    User = get_user_model()
    ensure_builtin_admin()
    if request.method == "GET":
        users = User.objects.prefetch_related("groups").order_by("id")
        return Response(SystemUserSerializer(users, many=True).data)

    serializer = SystemUserSerializer(data=request.data)
    if not serializer.is_valid():
        return bad_request(first_serializer_error(serializer.errors))
    user = serializer.save()
    return Response(SystemUserSerializer(user).data, status=status.HTTP_201_CREATED)


@api_view(["GET", "PUT", "DELETE"])
def system_user_detail(request, user_id: int):
    staff_error = require_staff(request)
    if staff_error:
        return staff_error

    User = get_user_model()
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({"error": "用户不存在"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(SystemUserSerializer(user).data)

    if request.method == "DELETE":
        if user.id == request.user.id:
            return bad_request("不能删除当前登录用户")
        if is_builtin_admin_user(user):
            return bad_request("内置管理员不允许删除")
        user.delete()
        return Response({"deleted": True})

    serializer = SystemUserSerializer(user, data=request.data, partial=True)
    if not serializer.is_valid():
        return bad_request(first_serializer_error(serializer.errors))
    saved_user = serializer.save()
    if is_builtin_admin_user(saved_user):
        saved_user = ensure_builtin_admin()
    return Response(SystemUserSerializer(saved_user).data)


@api_view(["GET", "POST"])
def roles(request):
    staff_error = require_staff(request)
    if staff_error:
        return staff_error

    if request.method == "GET":
        return Response(RoleSerializer(Group.objects.prefetch_related("permissions").order_by("id"), many=True).data)

    serializer = RoleSerializer(data=request.data)
    if not serializer.is_valid():
        return bad_request(first_serializer_error(serializer.errors))
    return Response(RoleSerializer(serializer.save()).data, status=status.HTTP_201_CREATED)


@api_view(["GET", "PUT", "DELETE"])
def role_detail(request, role_id: int):
    staff_error = require_staff(request)
    if staff_error:
        return staff_error

    try:
        role = Group.objects.get(id=role_id)
    except Group.DoesNotExist:
        return Response({"error": "角色不存在"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(RoleSerializer(role).data)

    if request.method == "DELETE":
        role.delete()
        return Response({"deleted": True})

    serializer = RoleSerializer(role, data=request.data, partial=True)
    if not serializer.is_valid():
        return bad_request(first_serializer_error(serializer.errors))
    return Response(RoleSerializer(serializer.save()).data)


@api_view(["GET"])
def permissions(request):
    staff_error = require_staff(request)
    if staff_error:
        return staff_error

    queryset = Permission.objects.select_related("content_type").order_by("content_type__app_label", "codename")
    return Response(PermissionSerializer(queryset, many=True).data)


@api_view(["GET", "POST"])
def system_settings(request):
    staff_error = require_staff(request)
    if staff_error:
        return staff_error

    if request.method == "GET":
        return Response(SystemSettingSerializer(SystemSetting.objects.all(), many=True).data)

    serializer = SystemSettingSerializer(data=request.data)
    if not serializer.is_valid():
        return bad_request(first_serializer_error(serializer.errors))
    return Response(SystemSettingSerializer(serializer.save()).data, status=status.HTTP_201_CREATED)


@api_view(["GET", "PUT", "DELETE"])
def system_setting_detail(request, setting_key: str):
    staff_error = require_staff(request)
    if staff_error:
        return staff_error

    try:
        setting = SystemSetting.objects.get(key=setting_key)
    except SystemSetting.DoesNotExist:
        return Response({"error": "系统设置不存在"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(SystemSettingSerializer(setting).data)

    if request.method == "DELETE":
        setting.delete()
        return Response({"deleted": True})

    serializer = SystemSettingSerializer(setting, data=request.data, partial=True)
    if not serializer.is_valid():
        return bad_request(first_serializer_error(serializer.errors))
    return Response(SystemSettingSerializer(serializer.save()).data)


def first_serializer_error(errors):
    if isinstance(errors, dict):
        first = next(iter(errors.values()))
        if isinstance(first, list) and first:
            return first[0]
        return first
    if isinstance(errors, list) and errors:
        return errors[0]
    return errors


def bounded_int(value, *, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return min(max(number, minimum), maximum)
