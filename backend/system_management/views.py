from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.db.models import CharField
from django.db.models.functions import Cast
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from accounts.permissions import require_staff
from operations.responses import bad_request, bounded_int, not_found, serializer_bad_request

from .models import LoginLog, SystemSetting
from .serializers import LoginLogSerializer, PermissionSerializer, RoleSerializer, SystemSettingSerializer, SystemUserSerializer
from .services import FEATURE_PERMISSION_CODES, ensure_builtin_admin, ensure_feature_permissions, is_builtin_admin_user


@api_view(["GET"])
def login_logs(request):
    staff_error = require_staff(request)
    if staff_error:
        return staff_error

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
        return serializer_bad_request(serializer)
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
        return not_found("用户不存在")

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
        return serializer_bad_request(serializer)
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
        ensure_feature_permissions()
        return Response(RoleSerializer(Group.objects.prefetch_related("permissions").order_by("id"), many=True).data)

    serializer = RoleSerializer(data=request.data)
    if not serializer.is_valid():
        return serializer_bad_request(serializer)
    return Response(RoleSerializer(serializer.save()).data, status=status.HTTP_201_CREATED)


@api_view(["GET", "PUT", "DELETE"])
def role_detail(request, role_id: int):
    staff_error = require_staff(request)
    if staff_error:
        return staff_error

    try:
        role = Group.objects.get(id=role_id)
    except Group.DoesNotExist:
        return not_found("角色不存在")

    if request.method == "GET":
        return Response(RoleSerializer(role).data)

    if request.method == "DELETE":
        role.delete()
        return Response({"deleted": True})

    serializer = RoleSerializer(role, data=request.data, partial=True)
    if not serializer.is_valid():
        return serializer_bad_request(serializer)
    return Response(RoleSerializer(serializer.save()).data)


@api_view(["GET"])
def permissions(request):
    staff_error = require_staff(request)
    if staff_error:
        return staff_error

    queryset = Permission.objects.select_related("content_type").order_by("content_type__app_label", "codename")
    ensure_feature_permissions()
    queryset = queryset.filter(codename__in=FEATURE_PERMISSION_CODES).order_by("id")
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
        return serializer_bad_request(serializer)
    return Response(SystemSettingSerializer(serializer.save()).data, status=status.HTTP_201_CREATED)


@api_view(["GET", "PUT", "DELETE"])
def system_setting_detail(request, setting_key: str):
    staff_error = require_staff(request)
    if staff_error:
        return staff_error

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
