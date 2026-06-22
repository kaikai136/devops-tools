from rest_framework import status
from rest_framework.response import Response


def require_login(request):
    if not request.user.is_authenticated:
        return Response({"error": "请先登录"}, status=status.HTTP_401_UNAUTHORIZED)
    return None


def require_staff(request):
    auth_error = require_login(request)
    if auth_error:
        return auth_error
    if not request.user.is_staff:
        return Response({"error": "没有用户管理权限"}, status=status.HTTP_403_FORBIDDEN)
    return None
