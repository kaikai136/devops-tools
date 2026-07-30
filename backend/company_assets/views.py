from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from accounts.permissions import require_feature_permission
from operations.responses import get_object_or_error, serializer_bad_request

from .models import CompanyDevice
from .serializers import CompanyDeviceSerializer


def company_device_permission(request, action_key: str | None = None):
    return require_feature_permission(request, "companyDevices", action_key, "没有设备管理权限")


@api_view(["GET", "POST"])
def company_devices(request):
    action = "create" if request.method == "POST" else None
    auth_error = company_device_permission(request, action)
    if auth_error:
        return auth_error

    if request.method == "GET":
        devices = CompanyDevice.objects.select_related("created_by").all()
        return Response(CompanyDeviceSerializer(devices, many=True).data)

    serializer = CompanyDeviceSerializer(data=request.data)
    if not serializer.is_valid():
        return serializer_bad_request(serializer)
    creator = request.user if request.user.is_authenticated else None
    device = serializer.save(created_by=creator)
    return Response(CompanyDeviceSerializer(device).data, status=status.HTTP_201_CREATED)


@api_view(["PUT", "DELETE"])
def company_device_detail(request, device_id: int):
    action = "delete" if request.method == "DELETE" else "edit"
    auth_error = company_device_permission(request, action)
    if auth_error:
        return auth_error

    device, error = get_object_or_error(
        CompanyDevice,
        queryset=CompanyDevice.objects.select_related("created_by"),
        id=device_id,
        error_message="设备不存在",
    )
    if error:
        return error

    if request.method == "DELETE":
        device.delete()
        return Response({"deleted": True})

    serializer = CompanyDeviceSerializer(device, data=request.data, partial=True)
    if not serializer.is_valid():
        return serializer_bad_request(serializer)
    device = serializer.save()
    return Response(CompanyDeviceSerializer(device).data)
