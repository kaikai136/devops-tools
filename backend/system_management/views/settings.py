from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from accounts.permissions import require_login
from operations.responses import get_object_or_error, serializer_bad_request

from ..models import SystemSetting
from ..serializers import DISPLAY_SETTING_KEYS, PUBLIC_DISPLAY_SETTING_KEYS, SystemSettingSerializer
from ..services import record_operation_log
from .common import require_system_permission


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

    setting, error = get_object_or_error(SystemSetting, key=setting_key, error_message="系统设置不存在")
    if error:
        return error

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
